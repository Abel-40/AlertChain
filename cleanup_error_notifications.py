"""
Cleanup script to fix existing notifications with raw error messages.
Run this once to sanitize all existing notification messages.

Usage:
    python cleanup_error_notifications.py
"""
import asyncio
from sqlalchemy import select, update
from app.db.db import get_db
from app.models.model import Notification


def _get_user_friendly_email_error(error_str: str, asset_id: str = "alert") -> str:
    """
    Convert technical email errors into user-friendly messages.
    """
    error_lower = error_str.lower()
    
    # Connection/Network errors
    if any(keyword in error_lower for keyword in ['errno 111', 'connection refused', 'connect call failed']):
        return f"Email service temporarily unavailable. Your {asset_id} alert was triggered but notification email could not be sent. Our team has been notified."
    
    # Timeout errors
    if any(keyword in error_lower for keyword in ['timeout', 'timed out', 'connection timed out']):
        return f"Email delivery delayed due to network timeout. Your {asset_id} alert was triggered. We'll continue trying to send the notification."
    
    # SSL/TLS errors
    if any(keyword in error_lower for keyword in ['ssl', 'tls', 'certificate', '503']):
        return f"Email notification failed due to security configuration. Your {asset_id} alert was triggered. Please contact support."
    
    # Authentication errors
    if any(keyword in error_lower for keyword in ['535', 'authentication failed', 'auth failed', 'invalid login', 'invalid password']):
        if 'connect call failed' not in error_lower and 'errno 111' not in error_lower:
            return f"Email notification failed due to configuration issue. Your {asset_id} alert was triggered. Please contact support to resolve this."
    
    # SMTP/Server errors
    if any(keyword in error_lower for keyword in ['smtp', 'mail server', 'mail service']):
        if 'connect call failed' not in error_lower and 'errno 111' not in error_lower:
            return f"Email service is experiencing issues. Your {asset_id} alert was triggered successfully, but notification email is delayed."
    
    # Rate limiting
    if any(keyword in error_lower for keyword in ['rate limit', 'too many', '421', '450']):
        return f"Email notification delayed due to high volume. Your {asset_id} alert was triggered. We'll send the notification shortly."
    
    # Recipient issues
    if any(keyword in error_lower for keyword in ['recipient', 'invalid email', 'no such user', '550']):
        return f"Could not deliver email notification for {asset_id} alert. Please verify your email address in profile settings."
    
    # Generic fallback - only if it looks like a technical error
    if any(keyword in error_lower for keyword in ['exception', 'error', 'traceback', 'errno', 'port', 'ip address']):
        return f"Email notification for {asset_id} alert could not be delivered at this time. Your alert is still active and monitoring. Our team has been notified of this issue."
    
    # If it's already a user-friendly message, leave it alone
    return error_str


async def cleanup_failed_notifications():
    """Find and fix all FAILED notifications with technical error messages."""
    
    print("Starting notification cleanup...")
    
    async for db in get_db():
        try:
            # Get all FAILED notifications
            stmt = select(Notification).where(Notification.status == "FAILED")
            result = await db.scalars(stmt)
            failed_notifications = result.all()
            
            print(f"Found {len(failed_notifications)} failed notifications")
            
            updated_count = 0
            
            for notification in failed_notifications:
                original_message = notification.message
                
                # Check if message contains technical details
                is_technical = any(keyword in original_message.lower() for keyword in [
                    'errno', 'connect call failed', 'connection refused', 
                    'smtp.gmail.com', 'port 587', 'traceback',
                    'exception raised', 'credentials or email service'
                ])
                
                if is_technical:
                    # Try to extract asset_id from the message
                    asset_id = "alert"
                    if 'alert for' in original_message.lower():
                        # Try to extract the asset name
                        parts = original_message.lower().split('alert for')
                        if len(parts) > 1:
                            asset_part = parts[1].split()[0] if parts[1] else "alert"
                            asset_id = asset_part
                    
                    # Generate user-friendly message
                    friendly_message = _get_user_friendly_email_error(original_message, asset_id)
                    
                    # Update the notification
                    notification.message = friendly_message
                    updated_count += 1
                    
                    print(f"✓ Updated notification {notification.id}")
                    print(f"  Old: {original_message[:80]}...")
                    print(f"  New: {friendly_message[:80]}...")
            
            await db.commit()
            
            print(f"\n✅ Cleanup complete!")
            print(f"   Total failed notifications: {len(failed_notifications)}")
            print(f"   Updated with friendly messages: {updated_count}")
            
        except Exception as e:
            print(f"❌ Error during cleanup: {e}")
            await db.rollback()
        finally:
            break  # Exit the async generator


if __name__ == "__main__":
    print("=" * 60)
    print("NOTIFICATION ERROR MESSAGE CLEANUP")
    print("=" * 60)
    print()
    
    asyncio.run(cleanup_failed_notifications())
    
    print()
    print("=" * 60)
    print("Cleanup finished!")
    print("=" * 60)
