"""Quick test to diagnose DATABASE_URL connection issue."""

import os
from dotenv import load_dotenv
from urllib.parse import urlparse

# Load .env
load_dotenv()

print("=" * 60)
print("🔍 DATABASE_URL DIAGNOSTIC TEST")
print("=" * 60)

# Get DATABASE_URL
db_url = os.getenv("DATABASE_URL")

if not db_url:
    print("\n❌ ERROR: DATABASE_URL not found in environment")
    print("   Make sure .env file exists and has DATABASE_URL set")
    exit(1)

print(f"\n📋 Raw DATABASE_URL from .env:")
print(f"   {db_url[:50]}...")  # Show first 50 chars only

# Parse URL
try:
    parsed = urlparse(db_url)

    print(f"\n🔍 Parsed URL components:")
    print(f"   Scheme: {parsed.scheme}")
    print(f"   Username: {parsed.username}")
    print(f"   Password: {'***' + parsed.password[-4:] if parsed.password else 'None'}")
    print(f"   Hostname: {parsed.hostname}")
    print(f"   Port: {parsed.port}")
    print(f"   Database: {parsed.path}")

    if not parsed.hostname:
        print(f"\n❌ ERROR: Hostname is None!")
        print(f"   This usually means the URL format is incorrect")
        print(f"\n💡 Expected format:")
        print(f"   postgresql://postgres:PASSWORD@db.xxxxx.supabase.co:5432/postgres")
        exit(1)

except Exception as e:
    print(f"\n❌ ERROR parsing URL: {e}")
    exit(1)

# Test DNS resolution
print(f"\n🌐 Testing DNS resolution for: {parsed.hostname}")
try:
    import socket
    ip = socket.gethostbyname(parsed.hostname)
    print(f"   ✅ Resolved to IP: {ip}")
except socket.gaierror as e:
    print(f"   ❌ DNS resolution failed: {e}")
    print(f"\n💡 Possible causes:")
    print(f"   1. No internet connection")
    print(f"   2. Supabase hostname is incorrect")
    print(f"   3. Firewall blocking DNS queries")
    exit(1)

# Test TCP connection
print(f"\n🔌 Testing TCP connection to {parsed.hostname}:{parsed.port}")
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    result = sock.connect_ex((parsed.hostname, parsed.port))
    sock.close()

    if result == 0:
        print(f"   ✅ TCP connection successful")
    else:
        print(f"   ❌ Cannot connect to port {parsed.port}")
        print(f"   Error code: {result}")
except Exception as e:
    print(f"   ❌ Connection test failed: {e}")

# Try actual database connection
print(f"\n🗄️  Testing PostgreSQL connection...")
try:
    import psycopg

    # Build connection string
    conn_str = f"postgresql://{parsed.username}:{parsed.password}@{parsed.hostname}:{parsed.port}{parsed.path}"

    print(f"   Connecting to: {parsed.hostname}...")
    conn = psycopg.connect(conn_str, connect_timeout=10)

    # Test query
    with conn.cursor() as cur:
        cur.execute("SELECT version();")
        version = cur.fetchone()[0]

    conn.close()

    print(f"   ✅ PostgreSQL connection successful!")
    print(f"   Server version: {version[:50]}...")

    print("\n" + "=" * 60)
    print("🎉 ALL TESTS PASSED!")
    print("=" * 60)
    print("\nYour DATABASE_URL is working correctly.")
    print("You can now run: python run_migrations.py")

except psycopg.OperationalError as e:
    print(f"   ❌ PostgreSQL connection failed: {e}")
    print(f"\n💡 Check:")
    print(f"   1. Username is correct: {parsed.username}")
    print(f"   2. Password is correct (new password: MZ1BXmXNRJgFTEFV)")
    print(f"   3. Database name is correct: {parsed.path}")

except Exception as e:
    print(f"   ❌ Unexpected error: {e}")

print("=" * 60)
