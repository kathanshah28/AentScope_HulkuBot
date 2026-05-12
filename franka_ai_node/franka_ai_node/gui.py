import streamlit as st
import time
import json
import os
import threading

# Native ROS 2 Libraries
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient

# Import your custom interface
from custom_interfaces.action import ArmTask
from stsrc.llm_client import generate_ros_code

# Global Threading lock for ROS spinning
if 'ros_thread' not in st.session_state:
    st.session_state.ros_thread = None

# Page Configuration
st.set_page_config(
    page_title="AI ROS Code Generator",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .stTextArea textarea { background-color: #f0f2f6; color: #31333F; }
    .stButton>button { color: white; background-color: #FF4B4B; border-radius: 5px; width: 100%; }
    </style>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# ROS 2 NODE MANAGEMENT
# ---------------------------------------------------------
class StreamlitRosNode(Node):
    def __init__(self):
        super().__init__('streamlit_llm_node')
        self.action_client = ActionClient(self, ArmTask, '/arm_command')
        self.get_logger().info('Streamlit Node Initialized')

@st.cache_resource
def setup_ros():
    if not rclpy.ok():
        rclpy.init()
    node = StreamlitRosNode()
    
    def spin_thread():
        rclpy.spin(node)
    
    thread = threading.Thread(target=spin_thread, daemon=True)
    thread.start()
    return node

try:
    ros_node = setup_ros()
    st.sidebar.success("✅ Connected to ROS 2 Network")
except Exception as e:
    st.sidebar.error(f"❌ ROS Init Failed: {e}")
    st.stop()

# ---------------------------------------------------------
# ACTION LOGIC
# ---------------------------------------------------------
def result_callback(future):
    result = future.result().result
    print(f"✅ Action Finished. Success: {result.success}")

def feedback_callback(feedback_msg):
    print(f"🔄 Feedback received")

def send_action_goal(json_string):
    if not ros_node.action_client.wait_for_server(timeout_sec=5.0):
        st.error("❌ Action Server '/arm_command' not available!")
        return

    try:
        data = json.loads(json_string)
        
        # --- LOGIC: Pass JSON as-is for Cleaning, Wrap it for Movement ---
        if "strategy" in data:
            final_json_str = json_string
        elif "num_cubes" in data:
            final_json_str = json_string
        else:
            # Wrap movement commands in the standard format
            json_command = {
                "move": data.get('joints'), 
                "gripper": [data['gripper']] if 'gripper' in data else None
            }
            final_json_str = json.dumps(json_command)
        
        goal_msg = ArmTask.Goal()
        goal_msg.json_command = final_json_str 

        print(f"⏳ Sending Goal: {final_json_str}")
        
        send_future = ros_node.action_client.send_goal_async(
            goal_msg, 
            feedback_callback=feedback_callback
        )
        send_future.add_done_callback(goal_response_callback)
        return True

    except Exception as e:
        st.error(f"Error parsing/sending: {e}")
        return False

def goal_response_callback(future):
    goal_handle = future.result()
    if not goal_handle.accepted:
        print("❌ Goal rejected")
        return
    print("✅ Goal accepted")
    result_future = goal_handle.get_result_async()
    result_future.add_done_callback(result_callback)

# ---------------------------------------------------------
# MAIN UI
# ---------------------------------------------------------
def main():
    with st.sidebar:
        st.title("⚙️ Settings")
        st.markdown("---")
        provider = st.radio("LLM Provider", ["Ollama", "Gemini", "Groq"], index=0, horizontal=True)
        
        api_key = None
        if provider == "Ollama":
            model_name = st.selectbox("Ollama Model", ["deepseek-coder:6.7b", "deepseek-r1:1.5b"], index=0)
        elif provider == "Gemini":
            model_name = st.selectbox("Gemini Model", ["gemini-2.5-flash"], index=0)
            api_key = st.text_input("API Key", type="password") or os.getenv("GEMINI_API_KEY")
        else:
            model_name = st.selectbox("Groq Model", ["llama-3.1-8b-instant"], index=0)
            api_key = st.text_input("API Key", type="password") or os.getenv("GROQ_API_KEY")

        if st.button("Clear Chat"):
            st.session_state.messages = []
            st.rerun()

    st.title("🤖 Robot Command Chat")
    
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            if msg["role"] == "assistant" and msg["content"].strip().startswith("{"):
                st.code(msg["content"], language="json")
            else:
                st.markdown(msg["content"])

    if prompt := st.chat_input("Describe task..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.chat_message("user").markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Analyzing Intent..."):
                
                # 1. ROUTER STEP: Just send the KEY "ROUTER"
                router_response = generate_ros_code(
                    prompt, model_name, provider.lower(), api_key, 
                    prompt_type="ROUTER"
                )
                
                # Parse Router Decision
                try:
                    router_json = json.loads(router_response)
                    intent = router_json.get("task_type", "MOVEMENT")
                    print(f"intent from router prompt: {intent}")
                except:
                    intent = "MOVEMENT" # Fallback

                # 2. EXPERT STEP: Send the KEY "CLEANER" or "MOVEMENT"
                if intent == "CLEANING":
                    st.caption(f"🧠 Detected Task: {intent} (Routing to Cleaner Expert)")
                    response = generate_ros_code(
                        prompt, model_name, provider.lower(), api_key, 
                        prompt_type="CLEANER"
                    )
                elif intent == "MOVEMENT":
                    st.caption(f"🧠 Detected Task: {intent} (Routing to Movement Expert)")
                    response = generate_ros_code(
                        prompt, model_name, provider.lower(), api_key, 
                        prompt_type="MOVEMENT"
                    )
                else:
                    st.caption(f"🧠 Detected Task: {intent} (Routing to Spawner Expert)")
                    response = generate_ros_code(
                        prompt, model_name, provider.lower(), api_key, 
                        prompt_type="SPAWNER"
                    )
                
                print(f"response from expert prompt: {response}")
                
                # 3. EXECUTE
                if response.strip().startswith("{"):
                    st.code(response, language="json")
                    success = send_action_goal(response)
                    if success:
                        st.toast(f"Executing {intent} Task!", icon="🚀")
                elif response.startswith("Error"):
                    st.error(response)
                else:
                    st.markdown(response)
                
                st.session_state.messages.append({"role": "assistant", "content": response})

if __name__ == "__main__":
    main()