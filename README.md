# backend
# токен авторизации + чатбот 

curl -X 'POST' \
  'http://127.0.0.1:8080/authapp/register' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "email": "user2@example.com",
  "phone": "string",
  "firstname": "string",
  "middlename": "string",
  "lastname": "string",
  "password": "string",
  "repeatPassword": "string"
}'
curl -X 'POST' \
  'http://127.0.0.1:8080/authapp/login' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "email": "user2@example.com",
  "password": "string"
}'

# вставить токен сюда 
ws://localhost:8080/ws?token=
