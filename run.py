#!/usr/bin/env python3
"""
Simple script to run the CheeseShirts API server
"""

import uvicorn
from config import Config

if __name__ == "__main__":
    config = Config()
    
    print("Starting CheeseShirts API...")
    print(f"Server will be available at: http://{config.HOST}:{config.PORT}")
    print(f"API Documentation: http://{config.HOST}:{config.PORT}/docs")
    print(f"Debug mode: {config.DEBUG}")
    print("-" * 50)
    
    uvicorn.run(
        "main:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.DEBUG,
        log_level="info" if not config.DEBUG else "debug"
    )
