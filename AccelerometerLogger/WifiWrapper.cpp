#include <ESP8266WiFi.h>
#include "WiFiWrapper.h"
#include "StatusLED.h"
#include <Esp.h>

WifiWrapper::WifiWrapper(int ledPin) {
  led = StatusLED(ledPin);
}

bool WifiWrapper::wifiConnect(const char* ssid, const char* password) {
  int times = 0;
  WiFi.begin(ssid, password);
  int status = WiFi.status();
  while (status != WL_CONNECTED && times < MAX_TIMEOUT) {
    switch (status) {
      case WL_NO_SHIELD : Serial.println("Couldn't find WiFi hardware!"); break;
      case WL_NO_SSID_AVAIL : Serial.println("Couldn't find the supplied SSID"); break;
      case WL_CONNECT_FAILED : Serial.println("Couldn't connect to the supplised SSID"); break;
      case WL_IDLE_STATUS : Serial.println("Attempting to connect"); break;
      default : Serial.println("Waiting to connect");
    }
    status = WiFi.status();
    delay(800);
    yield();
    led.pulse(2);
    times++;
  }
  if (status != WL_CONNECTED && times >= MAX_TIMEOUT) {
    return false;
  }
  return true;
}

bool WifiWrapper::serverConnect(IPAddress ip, int port) {
  Serial.println("Attempting to connect client");
  if (!client.connect(ip, port)) return false;
//  memset(response_buffer, 0, 200);
//  Serial.println("Sending hello");
//  client.println("Hello!");
  return true;
}

bool WifiWrapper::sendKeepalive(void) {
  client.println(OPCODE_KEEPALIVE);
}

bool WifiWrapper::send(long timestamp, int x, int y, int z) {
  writesSinceFlush++;
  if (!client.connected()) return false;
  int currentLength = strlen(send_buffer);
  send_buffer[currentLength] = ' ';
  sprintf(&send_buffer[currentLength + 1], "%lu", timestamp);
  currentLength = strlen(send_buffer);
  send_buffer[currentLength] = ' ';
  sprintf(&send_buffer[currentLength + 1], "%i", x);
  currentLength = strlen(send_buffer);
  send_buffer[currentLength] = ' ';
  sprintf(&send_buffer[currentLength + 1], "%i", y);
  currentLength = strlen(send_buffer);
  send_buffer[currentLength] = ' ';
  sprintf(&send_buffer[currentLength + 1], "%i", z);
  currentLength = strlen(send_buffer);
  send_buffer[currentLength] = ' ';
  if (strlen(send_buffer) >= SEND_BUFFER_WATERMARK) {
    flush();
  }
  return true;
}

void WifiWrapper::flush(void) {
  long startFlush = millis();
  client.println(send_buffer);
  memset(send_buffer, 0, SEND_BUFFER_LENGTH);
  Serial.print("Flushing ");
  Serial.print(writesSinceFlush);
  Serial.print(" data points for ");
  Serial.print(millis() - startFlush);
  Serial.println("ms");
  writesSinceFlush = 0;
}

int WifiWrapper::getCommand(void) {
  if (!client.connected()) return COMMAND_DISCONNECTED;
  if (!client.available()) return COMMAND_NONE;
  char opcode = client.read();
  // Serial.print("Opcode: " );
  // Serial.println(opcode);
  switch (opcode) {
    case OPCODE_KEEPALIVE : return COMMAND_KEEPALIVE; break;
    case OPCODE_START : return COMMAND_START; break;
    case OPCODE_HALT : return COMMAND_HALT; break;
    case OPCODE_CONFIGURE : 
      // Serial.println("Checking OPCODE_CONFIGURE");
      if (!client.available()) return COMMAND_CONFIG_ERROR; 
      if (!(client.peek() >= CONFIG_1HZ && client.peek() <= CONFIG_400HZ)) return COMMAND_CONFIG_ERROR;
      requestedRate = client.read();
      if (!(client.peek() >= CONFIG_2G && client.peek() <= CONFIG_16G)) return COMMAND_CONFIG_ERROR; 
      requestedRange = client.read();
      return COMMAND_CONFIGURE;
      break;
    default: return COMMAND_UNKNOWN; break;
  }
  return COMMAND_UNKNOWN;
}

