import sys
import os
from pathlib import Path
import uvicorn
from fastapi import FastAPI
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add the current directory to the Python path
sys.path.append(str(Path(__file__).parent))

try:
    from init_db import init_db
    from main import app
except ImportError as e:
    logger.error(f"Error importing modules: {e}")
    sys.exit(1)

def check_port(port):
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('127.0.0.1', port))
    sock.close()
    return result == 0

if __name__ == "__main__":
    try:
        # Initialize database
        logger.info("Initializing database...")
        init_db()
        logger.info("Database initialized successfully!")
        
        # Check if port is available
        port = 8000
        if check_port(port):
            logger.warning(f"Port {port} is already in use. Trying alternative port...")
            port = 8001
        
        # Run the application
        logger.info(f"Starting server on port {port}...")
        logger.info(f"Server will be available at http://127.0.0.1:{port}")
        logger.info("Press Ctrl+C to stop the server")
        
        uvicorn.run(
            "main:app",
            host="127.0.0.1",
            port=port,
            reload=True,
            log_level="info"
        )
    except Exception as e:
        logger.error(f"Error starting server: {e}")
        logger.error("\nTroubleshooting steps:")
        logger.error("1. Make sure no other application is using the port")
        logger.error("2. Check if your firewall is blocking the connection")
        logger.error("3. Try running as administrator")
        sys.exit(1) 