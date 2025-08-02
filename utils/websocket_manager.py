"""
WebSocket manager for real-time communication in the GUI application.
"""

import asyncio
import json
import threading
import time
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from utils.logger import setup_logger

class WebSocketManager:
    """Manages WebSocket-like communication for the GUI application."""
    
    def __init__(self):
        self.logger = setup_logger('WebSocketManager')
        self.callbacks: List[Callable] = []
        self.running = False
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.thread: Optional[threading.Thread] = None
        
    def add_callback(self, callback: Callable):
        """Add a callback function to receive broadcasts."""
        self.callbacks.append(callback)
        self.logger.info(f"Added callback, total callbacks: {len(self.callbacks)}")
    
    def remove_callback(self, callback: Callable):
        """Remove a callback function."""
        if callback in self.callbacks:
            self.callbacks.remove(callback)
            self.logger.info(f"Removed callback, total callbacks: {len(self.callbacks)}")
    
    async def broadcast(self, event_type: str, data: Any):
        """Broadcast a message to all registered callbacks."""
        try:
            message = {
                'type': event_type,
                'data': data,
                'timestamp': datetime.now().isoformat()
            }
            
            self.logger.debug(f"Broadcasting {event_type} to {len(self.callbacks)} callbacks")
            
            # Call all registered callbacks
            for callback in self.callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(message)
                    else:
                        callback(message)
                except Exception as e:
                    self.logger.error(f"Error in callback: {e}")
                    
        except Exception as e:
            self.logger.error(f"Error broadcasting message: {e}")
    
    def broadcast_sync(self, event_type: str, data: Any):
        """Synchronous broadcast for use from non-async contexts."""
        if self.loop and self.running:
            try:
                asyncio.run_coroutine_threadsafe(
                    self.broadcast(event_type, data), 
                    self.loop
                )
            except Exception as e:
                self.logger.error(f"Error in sync broadcast: {e}")
    
    def run_in_background(self):
        """Start the WebSocket manager in a background thread."""
        if self.running:
            self.logger.warning("WebSocket manager already running")
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._run_event_loop, daemon=True)
        self.thread.start()
        self.logger.info("WebSocket manager started in background thread")
    
    def _run_event_loop(self):
        """Run the asyncio event loop in the background thread."""
        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_forever()
        except Exception as e:
            self.logger.error(f"Error in event loop: {e}")
        finally:
            self.running = False
    
    def stop(self):
        """Stop the WebSocket manager."""
        self.running = False
        if self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)
        if self.thread:
            self.thread.join(timeout=5)
        self.logger.info("WebSocket manager stopped")