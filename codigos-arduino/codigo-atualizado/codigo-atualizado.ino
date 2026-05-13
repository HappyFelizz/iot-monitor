#include <Wire.h>
#include <Adafruit_MLX90614.h>
#include <Servo.h>

// ===== Sensores =====
#define TRIG_PIN 9
#define ECHO_PIN 10


Adafruit_MLX90614 mlx = Adafruit_MLX90614();

// ===== Servos =====
Servo servoRadar;
Servo servoPortao;

#define SERVO_RADAR_PIN 6
#define SERVO_PORTAO_PIN 5

// ===== Variáveis =====
long duracao;
float distancia;
float temperatura;

int angulo = 0;
bool fechouPortao = false;

void setup() {
  Serial.begin(9600);

  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);

  servoRadar.attach(SERVO_RADAR_PIN);
  servoPortao.attach(SERVO_PORTAO_PIN);

  mlx.begin();

  servoPortao.write(0); // portão aberto inicialmente
}

float medirDistancia() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);

  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  duracao = pulseIn(ECHO_PIN, HIGH);
  distancia = duracao * 0.034 / 2;

  return distancia;
}

void loop() {

  // varredura
  for (angulo = 0; angulo <= 180; angulo += 2) {

    servoRadar.write(angulo);
    delay(50);

    distancia = medirDistancia();
    temperatura = mlx.readObjectTempC();

    if (distancia < 30) {

      // lógica humano
      if (temperatura > 30 && temperatura < 40) {
        servoPortao.write(200); // fecha portão
        fechouPortao = true;
      } else {
        servoPortao.write(90); // mantém aberto
        fechouPortao = false;
      }

    } else {
      servoPortao.write(90);
      fechouPortao = false;
    }

    // ===== Monitor Serial =====
    Serial.print("Angulo: ");
    Serial.print(angulo);

    Serial.print(" | Distancia: ");
    Serial.print(distancia);
    Serial.print(" cm");

    Serial.print(" | Temp: ");
    Serial.print(temperatura);
    Serial.print(" C");

    Serial.print(" | Portao: ");
    if (fechouPortao) {
      Serial.println("FECHADO");
    } else {
      Serial.println("ABERTO");
    }
  }

  // varredura voltando
  for (angulo = 180; angulo >= 0; angulo -= 2) {

    servoRadar.write(angulo);
    delay(50);

    distancia = medirDistancia();
    temperatura = mlx.readObjectTempC();

    if (distancia < 30) {

      if (temperatura > 30 && temperatura < 40) {
        servoPortao.write(200);
        fechouPortao = true;
      } else {
        servoPortao.write(90);
        fechouPortao = false;
      }

    } else {
      servoPortao.write(90);
      fechouPortao = false;
    }

    Serial.print("Angulo: ");
    Serial.print(angulo);

    Serial.print(" | Distancia: ");
    Serial.print(distancia);
    Serial.print(" cm");

    Serial.print(" | Temp: ");
    Serial.print(temperatura);
    Serial.print(" C");

    Serial.print(" | Portao: ");
    if (fechouPortao) {
      Serial.println("FECHADO");
    } else {
      Serial.println("ABERTO");
    }
  }
}