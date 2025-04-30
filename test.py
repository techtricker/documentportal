from passlib.hash import bcrypt

hashed_password = bcrypt.hash("password")
print(hashed_password)
