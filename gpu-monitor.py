import os

import subprocess
import requests
import time
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("gpu_monitor.log"),
        logging.StreamHandler()
    ]
)

# Telegram Bot Config
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Monitoring Config
CHECK_INTERVAL = 300  # Check every 5 minutes
GPU_THRESHOLD = 5  # Alert if GPU usage is below 5%
MAX_RETRIES = 3  # Maximum number of retries for sending messages

def get_gpu_usage():
    """Returns the minimum GPU usage percentage (handles multiple GPUs)."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=10  # Add timeout to prevent hanging
        )
        if result.returncode != 0:
            logging.error(f"nvidia-smi command failed with error: {result.stderr}")
            return None
            
        usages = [int(x) for x in result.stdout.strip().split("\n")]
        min_usage = min(usages)  # Return the lowest GPU usage
        logging.info(f"GPU Usage: {min_usage}%")
        return min_usage
    except subprocess.TimeoutExpired:
        logging.error("nvidia-smi command timed out")
        return None
    except Exception as e:
        logging.error(f"Error getting GPU usage: {str(e)}")
        return None


def send_telegram_message(message, retry_count=0):
    """Sends an alert to Telegram with retry mechanism."""
    if retry_count >= MAX_RETRIES:
        logging.error(f"Failed to send Telegram message after {MAX_RETRIES} attempts")
        return False
        
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
        response = requests.post(url, data=data, timeout=10)
        
        if response.status_code == 200:
            logging.info("Telegram message sent successfully")
            return True
        else:
            logging.warning(f"Failed to send Telegram message: HTTP {response.status_code}")
            time.sleep(5 * (retry_count + 1))  # Exponential backoff
            return send_telegram_message(message, retry_count + 1)
            
    except requests.exceptions.RequestException as e:
        logging.error(f"Error sending Telegram message: {str(e)}")
        time.sleep(5 * (retry_count + 1))  # Exponential backoff
        return send_telegram_message(message, retry_count + 1)


def main():
    last_alert_time = 0
    alert_cooldown = 1800  # 30 minutes between alerts
    
    logging.info("GPU monitoring started")
    
    while True:
        try:
            usage = get_gpu_usage()
            
            # Only proceed if we got a valid reading
            if usage is not None:
                current_time = time.time()
                
                # Check if GPU usage is below threshold and we're not in cooldown period
                if usage < GPU_THRESHOLD and (current_time - last_alert_time) > alert_cooldown:
                    message = f"⚠️ GPU usage is low: {usage}% at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    send_success = send_telegram_message(message)
                    
                    if send_success:
                        last_alert_time = current_time
            
            # Sleep until next check
            time.sleep(CHECK_INTERVAL)
            
        except KeyboardInterrupt:
            logging.info("Monitoring stopped by user")
            break
        except Exception as e:
            logging.error(f"Unexpected error in main loop: {str(e)}")
            # Sleep a bit before retrying to avoid tight error loops
            time.sleep(60)


if __name__ == "__main__":
    main()
