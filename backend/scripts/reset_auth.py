import os
import sys

# Add project root to python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.models import User
from app.services.auth import get_password_hash, generate_totp_secret, get_totp_uri

def main():
    print("=" * 60)
    print(" TEIS - ADMINISTRATOR AUTH SETUP & RESET CLI ")
    print("=" * 60)

    username = input("Masukkan username baru (default: admin): ").strip()
    if not username:
        username = "admin"
        
    password = input("Masukkan password baru (minimal 8 karakter): ").strip()
    if len(password) < 8:
        print("Error: Password harus minimal 8 karakter.")
        sys.exit(1)
        
    totp_choice = input("Aktifkan 2FA (TOTP)? [Y/n]: ").strip().lower()
    enable_totp = totp_choice != 'n'

    db = SessionLocal()
    try:
        # Check if user already exists
        user = db.query(User).filter(User.username == username).first()
        
        # Hash password
        pwd_hash = get_password_hash(password)
        
        # Setup TOTP if enabled
        totp_secret = generate_totp_secret() if enable_totp else None
        
        if user:
            print(f"\nUser '{username}' sudah terdaftar. Melakukan update password...")
            user.password_hash = pwd_hash
            if enable_totp:
                user.totp_secret = totp_secret
            else:
                user.totp_secret = None
        else:
            print(f"\nMembuat akun pengguna baru '{username}'...")
            user = User(
                username=username,
                password_hash=pwd_hash,
                totp_secret=totp_secret
            )
            db.add(user)
            
        db.commit()
        print("Registrasi berhasil!")
        
        if enable_totp:
            print("\n" + "=" * 60)
            print(" INFORMASI DUA FAKTOR (2FA) ")
            print("=" * 60)
            print(f"Secret Key (Base32) : {totp_secret}")
            uri = get_totp_uri(totp_secret, username)
            print(f"Provisioning URI    : {uri}")
            print("\nPetunjuk:")
            print("1. Salin 'Secret Key' di atas ke aplikasi Google Authenticator / Authy.")
            print("2. Atau gunakan link 'Provisioning URI' untuk mengimpor otomatis.")
            print("=" * 60)
            
    except Exception as e:
        print(f"\nTerjadi kesalahan: {str(e)}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    main()
