# admin4 running on linux docker with X server 
xhost +local:
docker run --rm -e DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix -v ~:/root -v admin4:/admin4 admin4
