#include <Arduino.h>
#include <math.h>   
#include <Servo.h>  

//CNC CONFIG
const int PIN_STEP   = 3;   // X_STEP
const int PIN_DIR    = 6;   // X_DIR
const int PIN_ENABLE = 8;   

const int SERVO_PIN          = 11;  // Z+ header
const int SERVO_CLOSED_ANGLE = 0;   
const int SERVO_OPEN_ANGLE   = 90;  

Servo gateServo;

const long STEPS_PER_REV = 200;
const int  NUM_BINS      = 12;

long binStepPos[NUM_BINS];

long currentStepPos = 0;  
int  currentBin     = 0;

void stepMotor(long steps)
{
  bool dirCW = (steps >= 0);
  digitalWrite(PIN_DIR, dirCW ? HIGH : LOW);

  long count = labs(steps);
  for (long i = 0; i < count; i++) {
    digitalWrite(PIN_STEP, HIGH);
    delayMicroseconds(3000);   // slower / smoother
    digitalWrite(PIN_STEP, LOW);
    delayMicroseconds(3000);
  }
}

void moveToBin(int targetBin)
{
  if (targetBin < 0 || targetBin >= NUM_BINS) {
    Serial.print("Invalid bin: ");
    Serial.println(targetBin);
    return;
  }

  if (targetBin == currentBin) {
    Serial.println("Already at target bin.");
    return;
  }

  long targetPos  = binStepPos[targetBin];
  long deltaSteps = targetPos - currentStepPos;

  if (deltaSteps >  STEPS_PER_REV / 2)  deltaSteps -= STEPS_PER_REV;
  if (deltaSteps < -STEPS_PER_REV / 2)  deltaSteps += STEPS_PER_REV;

  Serial.print("Moving from bin ");
  Serial.print(currentBin);
  Serial.print(" to ");
  Serial.print(targetBin);
  Serial.print(" (steps = ");
  Serial.print(deltaSteps);
  Serial.println(")");

  stepMotor(deltaSteps);

  currentStepPos += deltaSteps;
  currentStepPos %= STEPS_PER_REV;
  if (currentStepPos < 0) currentStepPos += STEPS_PER_REV;

  currentBin = targetBin;

  Serial.println("MOVE_DONE");
}

void servoOpen()
{
  gateServo.write(SERVO_OPEN_ANGLE);
  Serial.println("SERVO_OPEN_DONE");
}

void servoClose()
{
  gateServo.write(SERVO_CLOSED_ANGLE);
  Serial.println("SERVO_CLOSE_DONE");
}

String inputBuffer;

void processCommand(const String &cmd)
{
  if (cmd.startsWith("BIN:")) {
    int idx = cmd.substring(4).toInt();
    moveToBin(idx);

  } else if (cmd == "SERVO:OPEN") {
    servoOpen();

  } else if (cmd == "SERVO:CLOSE") {
    servoClose();

  } else {
    Serial.print("Unknown command: ");
    Serial.println(cmd);
  }
}


void setup()
{
  Serial.begin(115200);

  pinMode(PIN_STEP, OUTPUT);
  pinMode(PIN_DIR, OUTPUT);
  pinMode(PIN_ENABLE, OUTPUT);

  //driver
  digitalWrite(PIN_ENABLE, LOW);

  for (int i = 0; i < NUM_BINS; i++) {
    double pos = (double)i * (double)STEPS_PER_REV / (double)NUM_BINS;
    binStepPos[i] = (long)lround(pos);
  }

  currentBin     = 0;
  currentStepPos = 0;

  //servo
  gateServo.attach(SERVO_PIN);
  gateServo.write(SERVO_CLOSED_ANGLE);

  Serial.println("Stepper + servo bin controller ready.");
  Serial.println("Use commands like: BIN:3, SERVO:OPEN, SERVO:CLOSE");
}


void loop()
{
  while (Serial.available() > 0) {
    char c = Serial.read();

    if (c == '\n' || c == '\r') {
      if (inputBuffer.length() > 0) {
        processCommand(inputBuffer);
        inputBuffer = "";
      }
    } else {
      inputBuffer += c;
      if (inputBuffer.length() > 50) {
        inputBuffer = "";
      }
    }
  }
}
