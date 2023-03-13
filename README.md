# SmartNotes

### The Collaborative Resource and Revision Platform

Requirements:

- Docker
- Internet Connection
- Free port 5000

### To Run:
1. open terminal in files folder
2. do 'docker-compose build' to create (This may take some time)
3. do 'docker-compose up' to run 
4. This will create and run a collection of docker containers called smartnotes
5. You can view the website by going to http://localhost:5000
6. Enable emails by following the instructions in files/config.py

### To Run Unit Tests Option 1:
1. Run the docker container 'smartnotes' created in the 'To Run' section.
2. Using Docker Desktop open the terminal of the 'web_server' container.
3. Run 'python -m pytest'

### To Run Unit Tests Option 2:
1. Run the docker container 'smartnotes' created in the 'To Run' section.
2. In terminal do 'docker ps -a'
3. Take note of the container id for the image 'smartnotes-web_server'
4. In terminal do 'docker exec \<container_id> python -m pytest'