from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.hash import bcrypt

# Secret key and algorithm
SECRET_KEY = "Parr@matta"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_password(plain_password, hashed_password):
    return bcrypt.verify(plain_password, hashed_password)

def get_password_hash(password):
    return bcrypt.hash(password)

def get_assignment_id_from_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assignment_id = payload.get("assignment")  
        if assignment_id is None:
            raise ValueError("Invalid token: no user ID")
        return assignment_id
    except JWTError:
        raise ValueError("Invalid token")
