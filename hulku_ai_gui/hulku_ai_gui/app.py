"""
HulkuBot AI Agent — Premium Streamlit Chat Interface
"""

import json
import os
import threading
import time

import streamlit as st

# ROS 2
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from custom_interfaces.action import ArmTask

# ═══════════════════════════════════════════════════════════
# PAGE CONFIG
# ═══════════════════════════════════════════════════════════
st.set_page_config(
    page_title="HulkuBot AI",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ═══════════════════════════════════════════════════════════
# CUSTOM CSS (PREMIUM DESIGN)
# ═══════════════════════════════════════════════════════════
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');

    /* Global Typography & Hide Defaults */
    html, body, [class*="st-"] {
        font-family: 'Outfit', sans-serif;
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Main App Background */
    .stApp {
        background: #0a0a0f;
        background-image: 
            radial-gradient(circle at 15% 50%, rgba(99, 102, 241, 0.08) 0%, transparent 50%),
            radial-gradient(circle at 85% 30%, rgba(168, 85, 247, 0.08) 0%, transparent 50%);
        color: #f1f5f9;
    }

    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background: rgba(15, 15, 20, 0.95);
        border-right: 1px solid rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(20px);
    }
    
    /* Bottom Block Background overrides */
    [data-testid="stBottom"], 
    [data-testid="stBottom"] > div,
    [data-testid="stBottomBlockContainer"] {
        background: transparent !important;
        background-color: transparent !important;
    }

    /* Input Container & Pill styling */
    .stChatInputContainer {
        padding-bottom: 20px !important;
        background: transparent !important;
    }
    .stChatInput > div {
        background: rgba(20, 20, 30, 0.8) !important;
        border: 1px solid rgba(99, 102, 241, 0.3) !important;
        border-radius: 20px !important;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2) !important;
        transition: all 0.3s ease;
    }
    .stChatInput > div:focus-within {
        border-color: #8b5cf6 !important;
        box-shadow: 0 0 15px rgba(139, 92, 246, 0.3) !important;
    }

    /* Force inner Streamlit/Baseweb elements to be transparent */
    .stChatInput [data-baseweb="textarea"],
    .stChatInput [data-baseweb="input"],
    .stChatInput [data-baseweb="base-input"] {
        background-color: transparent !important;
        background: transparent !important;
        border: none !important;
    }
    .stChatInput textarea {
        color: #f1f5f9 !important;
        background-color: transparent !important;
    }
    /* Hide the default send button background */
    .stChatInput button {
        background-color: transparent !important;
    }

    /* Gradient Text */
    .gradient-text {
        background: linear-gradient(135deg, #6366f1, #a855f7, #ec4899);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 700;
        font-size: 2.2rem;
        margin-bottom: 5px;
        letter-spacing: -0.5px;
    }

    .sub-text {
        color: #94a3b8;
        font-size: 0.9rem;
        margin-bottom: 20px;
    }

    /* Custom Chat Bubbles */
    .chat-container {
        display: flex;
        flex-direction: column;
        gap: 20px;
        margin-bottom: 30px;
    }
    
    .chat-bubble-wrapper {
        display: flex;
        align-items: flex-end;
        animation: fadeIn 0.4s cubic-bezier(0.16, 1, 0.3, 1);
    }
    
    .user-wrapper {
        justify-content: flex-end;
    }
    
    .ai-wrapper {
        justify-content: flex-start;
    }

    .avatar {
        width: 38px;
        height: 38px;
        min-width: 38px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 18px;
        margin: 0 12px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        border: 2px solid rgba(255,255,255,0.1);
    }

    .user-avatar {
        background: linear-gradient(135deg, #ec4899, #f43f5e);
    }

    .ai-avatar {
        background: linear-gradient(135deg, #3b82f6, #6366f1);
    }

    .chat-bubble {
        max-width: 75%;
        padding: 14px 20px;
        font-size: 0.95rem;
        line-height: 1.5;
        box-shadow: 0 4px 20px rgba(0,0,0,0.15);
    }

    .user-bubble {
        background: linear-gradient(135deg, #4f46e5, #7c3aed);
        color: white;
        border-radius: 20px 20px 4px 20px;
    }

    .ai-bubble {
        background: rgba(30, 30, 40, 0.85);
        color: #f1f5f9;
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 20px 20px 20px 4px;
        backdrop-filter: blur(12px);
    }

    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }

    /* Sidebar Items */
    .tool-badge {
        display: inline-block;
        padding: 4px 10px;
        background: rgba(99, 102, 241, 0.15);
        color: #a5b4fc;
        border: 1px solid rgba(99, 102, 241, 0.3);
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-bottom: 6px;
        margin-right: 6px;
    }

    .status-indicator {
        display: flex;
        align-items: center;
        padding: 10px 15px;
        border-radius: 8px;
        font-weight: 600;
        font-size: 0.9rem;
        margin-bottom: 20px;
    }
    .status-on {
        background: rgba(16, 185, 129, 0.1);
        border: 1px solid rgba(16, 185, 129, 0.3);
        color: #34d399;
    }
    .status-off {
        background: rgba(239, 68, 68, 0.1);
        border: 1px solid rgba(239, 68, 68, 0.3);
        color: #f87171;
    }
    .status-dot {
        width: 8px; height: 8px; border-radius: 50%; margin-right: 10px;
    }
    .status-on .status-dot { background: #34d399; box-shadow: 0 0 8px #34d399; }
    .status-off .status-dot { background: #f87171; box-shadow: 0 0 8px #f87171; }

    /* Button Override */
    .stButton > button {
        width: 100%;
        background: rgba(255, 255, 255, 0.05) !important;
        color: #e2e8f0 !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 10px !important;
        font-weight: 500 !important;
        transition: all 0.2s;
    }
    .stButton > button:hover {
        background: rgba(255, 255, 255, 0.1) !important;
        border-color: #f43f5e !important;
        color: #f43f5e !important;
    }

    /* Microphone Recorder Base Styles */
    iframe[title="audio_recorder_streamlit.audio_recorder"] {
        background-color: transparent !important;
        border: none !important;
        filter: invert(1) hue-rotate(180deg);
        opacity: 0.8;
        transition: opacity 0.2s;
        margin-top: 5px;
    }
    iframe[title="audio_recorder_streamlit.audio_recorder"]:hover {
        opacity: 1.0;
    }
</style>

<script>
// This script runs continuously in the parent window to perfectly integrate the microphone
function moveMic() {
    const parent = window.parent.document;
    const audioIframe = parent.querySelector('iframe[title="audio_recorder_streamlit.audio_recorder"]');
    const sendBtn = parent.querySelector('[data-testid="stChatInputSubmitButton"]');
    
    if (audioIframe && sendBtn) {
        const sendWrapper = sendBtn.parentNode;
        
        // If the mic is not already perfectly placed in the sendWrapper
        if (audioIframe.parentNode !== sendWrapper) {
            
            // 1. Hide the original Streamlit wrapper so it doesn't create a blank black bar
            const stContainer = audioIframe.closest('.element-container');
            if (stContainer) {
                // Hide the parent of the element container to completely remove the block
                const verticalBlock = stContainer.parentNode;
                if(verticalBlock) verticalBlock.style.display = 'none';
            }
            
            // 2. Style the iframe to fit natively
            audioIframe.style.position = "static";
            audioIframe.style.width = "45px";
            audioIframe.style.height = "45px";
            audioIframe.style.marginRight = "8px";
            
            // 3. Make the send wrapper a flexbox to hold both icons side-by-side
            sendWrapper.style.display = "flex";
            sendWrapper.style.alignItems = "center";
            sendWrapper.style.flexDirection = "row-reverse"; // Put mic on the left of the send button
            
            // 4. Move the iframe!
            sendWrapper.appendChild(audioIframe);
        }
    }
}
// Run periodically to ensure it attaches after React renders
setInterval(moveMic, 500);
</script>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════
# ROS 2 NODE
# ═══════════════════════════════════════════════════════════
class GUIRosNode(Node):
    def __init__(self):
        super().__init__('hulku_ai_gui_node')
        self.action_client = ActionClient(self, ArmTask, '/arm_command')
        self.get_logger().info('GUI ROS Node initialized')


@st.cache_resource
def setup_ros():
    """Initialize ROS 2 and create the action client node."""
    if not rclpy.ok():
        rclpy.init()
    node = GUIRosNode()

    def spin_thread():
        rclpy.spin(node)

    thread = threading.Thread(target=spin_thread, daemon=True)
    thread.start()
    return node


# ═══════════════════════════════════════════════════════════
# ACTION CLIENT LOGIC
# ═══════════════════════════════════════════════════════════
def send_command(node, user_message: str, feedback_placeholder, live_updates_container=None) -> dict:
    if not node.action_client.wait_for_server(timeout_sec=5.0):
        return {"success": False, "message": "ROS 2 action server '/arm_command' not found. Is the agent node running?"}

    # Thread-safe feedback sharing using a list queue
    shared_feedback_queue = []

    def feedback_callback(feedback_msg):
        # This is called from the ROS background thread
        shared_feedback_queue.append(feedback_msg.feedback.state)

    goal_msg = ArmTask.Goal()
    goal_msg.json_command = user_message

    send_future = node.action_client.send_goal_async(goal_msg, feedback_callback=feedback_callback)
    
    import time
    while not send_future.done():
        time.sleep(0.1)

    goal_handle = send_future.result()
    if not goal_handle or not goal_handle.accepted:
        return {"success": False, "message": "Goal was rejected by the agent."}

    result_future = goal_handle.get_result_async()
    
    # Increase timeout to 600 seconds (10 minutes) for long complex sequences with waits
    start_time = time.time()
    while not result_future.done():
        # Process all pending feedback messages
        while len(shared_feedback_queue) > 0:
            msg = shared_feedback_queue.pop(0)
            
            if msg.startswith("[USER_MSG]"):
                # The agent explicitly wants to tell the user something.
                content = msg[10:]
                
                # Append to session state so it survives reruns
                st.session_state.messages.append({"role": "assistant", "content": f"<b style='color: #a5b4fc;'>[Live Update]</b> {content}"})
                
                # Render it immediately inside the live container so the user sees it without waiting for the final response
                if live_updates_container:
                    live_updates_container.markdown(f"""
                    <div class="chat-bubble-wrapper ai-wrapper">
                        <div class="avatar ai-avatar">🤖</div>
                        <div class="chat-bubble ai-bubble" style="background: rgba(99, 102, 241, 0.1); border-color: rgba(99, 102, 241, 0.3);">
                            <b>Update:</b> {content}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                # Regular background tool call feedback
                feedback_placeholder.markdown(f"<span style='color: gray; font-size: 0.85em;'><i>{msg}</i></span>", unsafe_allow_html=True)
            
        time.sleep(0.1)
        if time.time() - start_time > 600.0:
            return {"success": False, "message": "Timed out waiting for agent response."}

    if result_future.result() is None:
        return {"success": False, "message": "Result was None."}

    result = result_future.result().result
    return {"success": result.success, "message": result.message}


# ═══════════════════════════════════════════════════════════
# RENDER CHAT HELPER
# ═══════════════════════════════════════════════════════════
def render_chat_message(role: str, content: str):
    """Renders a custom HTML chat bubble."""
    if role == "user":
        html = f"""
        <div class="chat-bubble-wrapper user-wrapper">
            <div class="chat-bubble user-bubble">{content}</div>
            <div class="avatar user-avatar">👤</div>
        </div>
        """
    else:
        # Determine prefix for success/failure styling if we want, but keeping it unified for now
        icon = "🤖" if "✅" in content else ("⚠️" if "❌" in content else "⚡")
        html = f"""
        <div class="chat-bubble-wrapper ai-wrapper">
            <div class="avatar ai-avatar">{icon}</div>
            <div class="chat-bubble ai-bubble">{content}</div>
        </div>
        """
    st.markdown(html, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════
# MAIN APP
# ═══════════════════════════════════════════════════════════
def main():
    try:
        ros_node = setup_ros()
        ros_connected = True
    except Exception as e:
        ros_connected = False
        ros_node = None

    # ─── SIDEBAR ──────────────────────────────────────────
    with st.sidebar:
        st.markdown('<div class="gradient-text">HulkuBot</div>', unsafe_allow_html=True)
        st.markdown('<div class="sub-text">Intelligent Robot Arm Controller</div>', unsafe_allow_html=True)
        
        # Status
        if ros_connected:
            st.markdown('<div class="status-indicator status-on"><div class="status-dot"></div>ROS 2 Connected</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="status-indicator status-off"><div class="status-dot"></div>ROS 2 Disconnected</div>', unsafe_allow_html=True)

        st.markdown("### 🔧 Active Tools")
        st.markdown("""
        <span class="tool-badge">move_joints</span>
        <span class="tool-badge">move_gripper</span>
        <span class="tool-badge">get_joint_states</span>
        <span class="tool-badge">go_home</span>
        <span class="tool-badge">buzzer</span>
        <span class="tool-badge">torque_mode</span>
        <span class="tool-badge">wait</span>
        """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        if st.button("🗑️ Clear Conversation"):
            st.session_state.messages = []
            st.rerun()

        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("### 💡 Suggestions")
        st.caption("• *Move the first joint to 45 degrees*")
        st.caption("• *Where are your joints right now?*")
        st.caption("• *Go home and beep the buzzer*")

    # ─── MAIN CHAT AREA ──────────────────────────────────
    # Spacer
    st.markdown("<br><br>", unsafe_allow_html=True)
    
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": "Hello! I am HulkuBot, your agentic robot assistant. What would you like me to do today?"}
        ]

    # Container for all chat messages
    st.markdown('<div class="chat-container">', unsafe_allow_html=True)
    for msg in st.session_state.messages:
        render_chat_message(msg["role"], msg["content"])
    st.markdown('</div>', unsafe_allow_html=True)

    # Chat input
    prompt = st.chat_input("Command the robot...")

    # Voice input (floating over the chat input via CSS)
    from audio_recorder_streamlit import audio_recorder
    audio_bytes = audio_recorder(
        text="",
        recording_color="#f43f5e",
        neutral_color="#a5b4fc",
        icon_name="microphone",
        icon_size="2x",
        key="voice_recorder"
    )

    # Process voice command
    if audio_bytes and st.session_state.get('last_audio_bytes') != audio_bytes:
        st.toast("🎙️ Audio captured successfully!", icon="✅")
        st.session_state['last_audio_bytes'] = audio_bytes
        
        if not ros_connected:
            st.error("System disconnected. Cannot send voice commands.")
        else:
            with st.spinner("🎙️ Transcribing voice via Google SpeechRecognition..."):
                try:
                    import speech_recognition as sr
                    import tempfile
                    import os
                    from pydub import AudioSegment

                    # Save to temp file to convert to wav
                    fd, temp_path = tempfile.mkstemp(suffix=".wav") # Streamlit audio bytes might be wav natively depending on how it's captured
                    with os.fdopen(fd, 'wb') as f:
                        f.write(audio_bytes)

                    # It's safer to ensure it is in wav format using pydub
                    # Since we don't know the exact format, we just let pydub figure it out
                    wav_path = temp_path + "_converted.wav"
                    audio = AudioSegment.from_file(temp_path)
                    audio.export(wav_path, format="wav")

                    recognizer = sr.Recognizer()
                    with sr.AudioFile(wav_path) as source:
                        audio_data = recognizer.record(source)
                        prompt_text = recognizer.recognize_google(audio_data).strip()

                    # cleanup
                    os.remove(temp_path)
                    os.remove(wav_path)

                except Exception as e:
                    st.error(f"Voice transcription failed: {e}")
                    prompt_text = None

            if prompt_text:
                # Save transcribed text to be injected into the chat box
                st.session_state.voice_transcription = prompt_text
                st.rerun()

    # If we have a voice transcription pending, inject it into the Streamlit chat input box
    if st.session_state.get("voice_transcription"):
        js_code = f"""
        <script>
            const chatInput = window.parent.document.querySelector('textarea[data-testid="stChatInputTextArea"]');
            if(chatInput) {{
                let nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value").set;
                nativeInputValueSetter.call(chatInput, `{st.session_state.voice_transcription}`);
                let ev = new Event('input', {{ bubbles: true}});
                chatInput.dispatchEvent(ev);
            }}
        </script>
        """
        import streamlit.components.v1 as components
        components.html(js_code, width=0, height=0)
        st.session_state.voice_transcription = None

    # Process text command
    if prompt and not st.session_state.get('processing_prompt'):
        if not ros_connected:
            st.error("System disconnected. Cannot send commands.")
            return

        # Add and render user message instantly
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # We rerun to make the input box clear and user message show up immediately,
        # but we also need to trigger the AI response. 
        # Streamlit execution flow trick: set a flag to process response on this run
        st.session_state.processing_prompt = prompt
        st.rerun()

    # Process AI response if pending
    if hasattr(st.session_state, 'processing_prompt') and st.session_state.processing_prompt:
        prompt = st.session_state.processing_prompt
        st.session_state.processing_prompt = None
        
        # Create a container for live chat updates
        live_updates_container = st.container()
        
        # Show an empty placeholder that will be filled with live feedback
        feedback_placeholder = st.empty()
        
        with st.spinner("⚡ Agent is reasoning and executing tools..."):
            result = send_command(ros_node, prompt, feedback_placeholder, live_updates_container)

        # Clear the feedback placeholder once finished
        feedback_placeholder.empty()

        if result["success"]:
            response_text = f"✅ {result['message']}"
        else:
            response_text = f"❌ {result['message']}"

        st.session_state.messages.append({"role": "assistant", "content": response_text})
        st.rerun()


if __name__ == "__main__":
    main()
