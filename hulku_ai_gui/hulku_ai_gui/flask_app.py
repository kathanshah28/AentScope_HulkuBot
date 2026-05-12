#!/usr/bin/env python3
"""
HulkuBot AI GUI — Flask Server with ROS 2 Integration
Replaces Streamlit with native HTML/CSS/JS for full browser API access.
"""

import os
import json
import time
import threading
import base64
from flask import Flask, render_template, request, jsonify, Response, stream_with_context

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from custom_interfaces.action import ArmTask
from sensor_msgs.msg import JointState


# ═══════════════════════════════════════════════════════════
# ROS 2 NODE
# ═══════════════════════════════════════════════════════════
class GUIRosNode(Node):
    def __init__(self):
        super().__init__('hulku_ai_gui_node')
        self.action_client = ActionClient(self, ArmTask, '/arm_command')
        self.joint_states = None
        self.create_subscription(JointState, '/joint_states', self._joint_cb, 10)
        self.get_logger().info('GUI ROS Node initialized')

    def _joint_cb(self, msg):
        self.joint_states = msg


# ═══════════════════════════════════════════════════════════
# GLOBALS
# ═══════════════════════════════════════════════════════════
ros_node = None
app = Flask(__name__,
            template_folder=os.path.join(os.path.dirname(__file__), 'templates'),
            static_folder=os.path.join(os.path.dirname(__file__), 'static'))
app.secret_key = 'hulkubot-secret'

# Chat history (in-memory)
chat_history = [
    {"role": "assistant", "content": "Welcome. I am HulkuBot — your agentic robot arm. System primed and ready."}
]


# ═══════════════════════════════════════════════════════════
# ROS 2 COMMAND EXECUTION (Streaming with feedback)
# ═══════════════════════════════════════════════════════════
def send_ros_command_stream(user_message: str):
    """Generator that yields SSE events: feedback lines then final result."""
    import queue

    global ros_node
    if ros_node is None:
        yield 'event: result\ndata: {"success": false, "message": "ROS 2 not connected."}\n\n'
        return

    if not ros_node.action_client.wait_for_server(timeout_sec=5.0):
        yield 'event: result\ndata: {"success": false, "message": "Agent action server not found."}\n\n'
        return

    feedback_q = queue.Queue()

    def feedback_cb(feedback_msg):
        feedback_q.put(feedback_msg.feedback.state)

    goal_msg = ArmTask.Goal()
    goal_msg.json_command = user_message

    send_future = ros_node.action_client.send_goal_async(
        goal_msg, feedback_callback=feedback_cb
    )

    while not send_future.done():
        time.sleep(0.05)

    goal_handle = send_future.result()
    if not goal_handle or not goal_handle.accepted:
        yield 'event: result\ndata: {"success": false, "message": "Goal rejected by agent."}\n\n'
        return

    result_future = goal_handle.get_result_async()
    start = time.time()

    while not result_future.done():
        # Drain feedback queue and yield each as SSE
        while not feedback_q.empty():
            msg = feedback_q.get_nowait()
            escaped = json.dumps(msg)
            yield f'event: feedback\ndata: {escaped}\n\n'

        time.sleep(0.1)
        if time.time() - start > 600:
            yield 'event: result\ndata: {"success": false, "message": "Timed out."}\n\n'
            return

    # Drain any remaining feedback
    while not feedback_q.empty():
        msg = feedback_q.get_nowait()
        escaped = json.dumps(msg)
        yield f'event: feedback\ndata: {escaped}\n\n'

    result = result_future.result().result
    result_json = json.dumps({"success": result.success, "message": result.message})
    yield f'event: result\ndata: {result_json}\n\n'


# ═══════════════════════════════════════════════════════════
# FLASK ROUTES
# ═══════════════════════════════════════════════════════════
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/chat', methods=['POST'])
def chat():
    """SSE streaming endpoint: sends feedback events then final result."""
    data = request.json
    user_msg = data.get('message', '').strip()
    if not user_msg:
        return jsonify({"error": "Empty message"}), 400

    chat_history.append({"role": "user", "content": user_msg})

    def generate():
        final_result = None
        for event in send_ros_command_stream(user_msg):
            yield event
            # Capture the final result for chat history
            if 'event: result' in event:
                data_line = event.split('data: ', 1)[1].strip()
                final_result = json.loads(data_line)

        # Append assistant reply to chat history
        if final_result:
            prefix = "✅" if final_result["success"] else "❌"
            chat_history.append({"role": "assistant", "content": f"{prefix} {final_result['message']}"})

    return Response(stream_with_context(generate()), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@app.route('/api/voice', methods=['POST'])
def voice():
    """Receive audio blob, transcribe via Groq Whisper, return text."""
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file"}), 400

    audio_file = request.files['audio']
    audio_bytes = audio_file.read()

    try:
        from groq import Groq
        client = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))
        transcription = client.audio.transcriptions.create(
            file=("recording.webm", audio_bytes),
            model="whisper-large-v3",
            language="en",
        )
        text = transcription.text.strip()
        return jsonify({"text": text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/joints')
def joints():
    """Return current joint states."""
    global ros_node
    if ros_node and ros_node.joint_states:
        js = ros_node.joint_states
        data = {name: round(pos, 3) for name, pos in zip(js.name, js.position)}
        return jsonify(data)
    return jsonify({})


@app.route('/api/history')
def history():
    """Return chat history."""
    return jsonify(chat_history)


@app.route('/api/clear', methods=['POST'])
def clear():
    """Clear chat history."""
    global chat_history
    chat_history = [
        {"role": "assistant", "content": "Workspace cleared. Ready for new commands."}
    ]
    return jsonify({"ok": True})


# ═══════════════════════════════════════════════════════════
# STARTUP
# ═══════════════════════════════════════════════════════════
def _generate_ssl_cert():
    """Generate a self-signed SSL cert so the browser allows mic access."""
    import subprocess
    import tempfile
    cert_dir = os.path.join(tempfile.gettempdir(), 'hulku_ssl')
    os.makedirs(cert_dir, exist_ok=True)
    certfile = os.path.join(cert_dir, 'cert.pem')
    keyfile = os.path.join(cert_dir, 'key.pem')
    if not os.path.exists(certfile):
        subprocess.run([
            'openssl', 'req', '-x509', '-newkey', 'rsa:2048',
            '-keyout', keyfile, '-out', certfile,
            '-days', '365', '-nodes',
            '-subj', '/CN=HulkuBot'
        ], check=True, capture_output=True)
    return certfile, keyfile


def start_app(host='0.0.0.0', port=5000):
    global ros_node

    # Init ROS 2
    if not rclpy.ok():
        rclpy.init()
    ros_node = GUIRosNode()

    # Spin ROS in background
    spin_thread = threading.Thread(target=rclpy.spin, args=(ros_node,), daemon=True)
    spin_thread.start()

    # Generate SSL cert for mic access (navigator.mediaDevices requires secure context)
    certfile, keyfile = _generate_ssl_cert()

    print(f"🚀 HulkuBot GUI running at https://localhost:{port}")
    print(f"   ⚠️  Accept the self-signed certificate warning in your browser.")
    app.run(host=host, port=port, debug=False, use_reloader=False,
            ssl_context=(certfile, keyfile))


if __name__ == '__main__':
    start_app()

