## Setup
`pip3 install -r requirements.txt`  
`cp -r _secrets.template _secrets`  
Update secrets with your data  

Setup redis
https://redis.io/docs/getting-started/installation/install-redis-on-linux/  
https://realpython.com/python-redis/  

Setup message db
`python3 utils/init_db.py`

Import messages from a Telegram chat export JSON:
`python3 utils/import_messages.py chat.json`

## Run
Start redis  
`sudo redis-server /etc/redis/6379.conf`  
  
Requires python 3.7+  
`python3 main.py`

Access the database directly  
`redis-cli -n 1`