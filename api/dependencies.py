from fastapi.security import OAuth2PasswordBearer

oauth_scheme1 = OAuth2PasswordBearer(tokenUrl="token")
