import os
import sys

# Add project root to python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.models import User
from app.services.auth import get_password_hash

def init_admin():
    db = SessionLocal()
    try:
        username = "admin"
        password = "securepassword"
        # We use a static base32 secret for 2FA in development: JBSWY3DPEHPK3PXP
        totp_secret = "JBSWY3DPEHPK3PXP"
        
        user = db.query(User).filter(User.username == username).first()
        pwd_hash = get_password_hash(password)
        
        if user:
            print(f"User '{username}' sudah ada. Memperbarui password...")
            user.password_hash = pwd_hash
            user.totp_secret = totp_secret
        else:
            print(f"Membuat user default '{username}'...")
            user = User(
                username=username,
                password_hash=pwd_hash,
                totp_secret=totp_secret
            )
            db.add(user)
            
        db.commit()
        print("Inisialisasi user default admin berhasil!")
        print(f"Username   : {username}")
        print(f"Password   : {password}")
        print(f"2FA Secret : {totp_secret} (Impor ke Google Authenticator)")
    except Exception as e:
        print(f"Gagal inisialisasi: {str(e)}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    init_admin()
