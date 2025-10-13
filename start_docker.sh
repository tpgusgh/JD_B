# default.conf에서 port와 baudrate 읽기
CONF_FILE="default.conf"
SERIAL_PORT=$(grep '^port' $CONF_FILE | cut -d '=' -f2 | tr -d ' ')
BAUDRATE=$(grep '^baud_rate' $CONF_FILE | cut -d '=' -f2 | tr -d ' ')

echo "🔌 Serial port: $SERIAL_PORT"
echo "⚙️ Baudrate: $BAUDRATE"

# 🔽 2. --build 인자가 있는 경우에만 빌드
if [[ "$1" == "--build" ]]; then
  echo "🛠 Building Docker image..."
  docker build -t serial-api .
else
  echo "🚀 Skipping build step"
fi
# Docker run with device binding
sudo docker run -it --rm \
  --v /dev/pts:/dev/pts  \
  -p 8000:8000 \
  -e SERIAL_PORT=$SERIAL_PORT \
  -e BAUDRATE=$BAUDRATE \
  serial-api
