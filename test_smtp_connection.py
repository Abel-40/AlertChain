"""
Diagnostic script to test SMTP connectivity from inside Docker container.
Run this to identify why email isn't working.

Usage:
    docker compose -f docker-compose.dev.yml exec fastapi python test_smtp_connection.py
"""
import socket
import sys

def test_dns():
    """Test if we can resolve smtp.gmail.com"""
    print("\n" + "="*60)
    print("TEST 1: DNS Resolution")
    print("="*60)
    try:
        ips = socket.getaddrinfo('smtp.gmail.com', 587)
        print("✅ DNS Resolution SUCCESS")
        print(f"   Found {len(ips)} address(es):")
        for ip in ips[:3]:  # Show first 3
            print(f"   - {ip[4][0]}")
        return True
    except socket.gaierror as e:
        print(f"❌ DNS Resolution FAILED")
        print(f"   Error: {e}")
        print("\n   FIX: Add DNS servers to docker-compose.dev.yml:")
        print("   dns:")
        print("     - 8.8.8.8")
        print("     - 8.8.4.4")
        return False

def test_ping():
    """Test basic connectivity using socket"""
    print("\n" + "="*60)
    print("TEST 2: Basic Connectivity (Port 587)")
    print("="*60)
    try:
        sock = socket.create_connection(('smtp.gmail.com', 587), timeout=10)
        print("✅ Connection SUCCESS")
        print(f"   Connected to: {sock.getpeername()}")
        sock.close()
        return True
    except socket.timeout:
        print("❌ Connection TIMEOUT")
        print("   Server didn't respond in 10 seconds")
        print("\n   POSSIBLE CAUSES:")
        print("   - Firewall blocking port 587")
        print("   - Network issue")
        return False
    except socket.gaierror as e:
        print(f"❌ DNS ERROR: {e}")
        print("\n   FIX: Check DNS configuration")
        return False
    except ConnectionRefusedError:
        print("❌ Connection REFUSED")
        print("   Server actively rejected the connection")
        return False
    except Exception as e:
        print(f"❌ ERROR: {type(e).__name__}: {e}")
        return False

def test_alternative_ports():
    """Test alternative SMTP ports"""
    print("\n" + "="*60)
    print("TEST 3: Alternative Ports")
    print("="*60)
    
    ports = {
        465: "SMTPS (SSL/TLS)",
        587: "SMTP (STARTTLS)",
        25: "SMTP (Plain)"
    }
    
    for port, description in ports.items():
        try:
            sock = socket.create_connection(('smtp.gmail.com', port), timeout=5)
            print(f"✅ Port {port} ({description}): OPEN")
            sock.close()
        except Exception as e:
            print(f"❌ Port {port} ({description}): {type(e).__name__}")

def test_email_config():
    """Test if email configuration is loaded"""
    print("\n" + "="*60)
    print("TEST 4: Email Configuration")
    print("="*60)
    try:
        from app.core.config import settings
        print(f"EMAIL: {settings.EMAIL}")
        print(f"MAIL_SERVER: {settings.MAIL_SERVER}")
        print(f"MAIL_PORT: {settings.MAIL_PORT}")
        print(f"MAIL_FROM_NAME: {settings.MAIL_FROM_NAME}")
        print(f"MAIL_PASSWORD set: {'✅ Yes' if settings.MAIL_PASSWORD else '❌ No'}")
        
        if settings.MAIL_PASSWORD:
            # Show first 4 and last 4 chars only for security
            pwd = settings.MAIL_PASSWORD
            masked = pwd[:4] + '*' * (len(pwd) - 8) + pwd[-4:] if len(pwd) > 8 else '***'
            print(f"MAIL_PASSWORD: {masked} ({len(pwd)} chars)")
            
            # Check if it looks like an App Password (16 chars, no spaces)
            clean_pwd = pwd.replace(' ', '')
            if len(clean_pwd) == 16 and clean_pwd.isalnum():
                print("✅ Password format looks correct (16 chars)")
            else:
                print(f"⚠️  WARNING: Password might be incorrect")
                print(f"   Gmail App Passwords are 16 characters")
                print(f"   Your password is {len(clean_pwd)} characters")
        
        return True
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        return False

def test_actual_smtp():
    """Test actual SMTP handshake"""
    print("\n" + "="*60)
    print("TEST 5: SMTP Handshake Test")
    print("="*60)
    try:
        import smtplib
        from app.core.config import settings
        
        print(f"Connecting to {settings.MAIL_SERVER}:{settings.MAIL_PORT}...")
        server = smtplib.SMTP(settings.MAIL_SERVER, settings.MAIL_PORT, timeout=10)
        server.starttls()
        print("✅ STARTTLS successful")
        
        print(f"Attempting login with {settings.EMAIL}...")
        server.login(settings.EMAIL, settings.MAIL_PASSWORD)
        print("✅ LOGIN successful!")
        server.quit()
        print("\n🎉 EMAIL CONFIGURATION IS WORKING!")
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ AUTHENTICATION FAILED")
        print(f"   Error: {e}")
        print("\n   FIX: You need a Gmail App Password, not your regular password")
        print("   1. Go to: https://myaccount.google.com/apppasswords")
        print("   2. Generate an App Password for 'Mail'")
        print("   3. Update MAIL_PASSWORD in your .env file")
        return False
    except smtplib.SMTPException as e:
        print(f"❌ SMTP ERROR: {e}")
        return False
    except Exception as e:
        print(f"❌ ERROR: {type(e).__name__}: {e}")
        return False

def main():
    print("\n" + "="*60)
    print("SMTP CONNECTIVITY DIAGNOSTIC TOOL")
    print("="*60)
    
    results = {}
    
    # Run tests
    results['DNS'] = test_dns()
    results['Connectivity'] = test_ping()
    
    if results['Connectivity']:
        test_alternative_ports()
        results['SMTP Handshake'] = test_actual_smtp()
    
    results['Config'] = test_email_config()
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    for test, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test:20s} {status}")
    
    print("\n" + "="*60)
    
    # Final recommendation
    if all(results.values()):
        print("🎉 ALL TESTS PASSED! Email should work.")
    else:
        print("⚠️  SOME TESTS FAILED. See recommendations above.")
        print("\nQUICK FIXES:")
        if not results.get('DNS'):
            print("1. Add DNS servers to docker-compose.dev.yml")
        if not results.get('Connectivity'):
            print("2. Check firewall/antivirus settings")
            print("   - Allow Docker through Windows Firewall")
            print("   - Check if port 587 is blocked")
        if not results.get('SMTP Handshake'):
            print("3. Generate Gmail App Password")
            print("   - Visit: https://myaccount.google.com/apppasswords")
            print("   - Update MAIL_PASSWORD in .env")
    
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
