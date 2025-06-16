# scripts/setup_ollama.py
"""Script to setup Ollama and download models"""

import subprocess
import sys
import time
import requests

def run_command(command, description):
    """Run a shell command"""
    print(f"🔧 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed: {e.stderr}")
        return False

def check_ollama_running():
    """Check if Ollama service is running"""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        return response.status_code == 200
    except:
        return False

def main():
    """Setup Ollama and download models"""
    print("🚀 Setting up Ollama for LLM Search Backend\n")
    
    # Check if Ollama is already installed
    if run_command("ollama --version", "Checking Ollama installation"):
        print("✅ Ollama is already installed")
    else:
        print("📥 Installing Ollama...")
        if sys.platform.startswith('linux') or sys.platform.startswith('darwin'):
            if not run_command("curl -fsSL https://ollama.ai/install.sh | sh", "Installing Ollama"):
                print("❌ Failed to install Ollama")
                return
        else:
            print("🪟 On Windows, please download Ollama from https://ollama.ai/download")
            return
    
    # Start Ollama service
    if not check_ollama_running():
        print("🔄 Starting Ollama service...")
        # Start Ollama in background
        subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Wait for service to start
        for i in range(30):  # Wait up to 30 seconds
            if check_ollama_running():
                print("✅ Ollama service started")
                break
            time.sleep(1)
        else:
            print("❌ Failed to start Ollama service")
            return
    else:
        print("✅ Ollama service is already running")
    
    # Download required models
    models_to_download = [
        "llama2:7b",  # Default model
        # "mistral:7b",  # Alternative model
        # "codellama:7b"  # Code-focused model
    ]
    
    for model in models_to_download:
        if run_command(f"ollama pull {model}", f"Downloading {model}"):
            print(f"✅ Model {model} downloaded successfully")
        else:
            print(f"❌ Failed to download {model}")
    
    # List available models
    if run_command("ollama list", "Listing available models"):
        pass
    
    print("\n🎉 Ollama setup completed!")
    print("💡 You can now start the search backend with: make dev")

if __name__ == "__main__":
    main()
