#include "DTS6012M.h"

void DTS6012M_Init(DTS6012M* dev)
{
    Wire.beginTransmission(DTS6012M_ADD);
    Wire.write(LASER_EN_ADD);
    Wire.write(0x00); // Stop laser initially
    Wire.endTransmission();
    dev->raw_distance = 0;
}

void DTS6012M_StartLaser()
{
    Wire.beginTransmission(DTS6012M_ADD);
    Wire.write(LASER_EN_ADD);
    Wire.write(0x01); // Start laser
    Wire.endTransmission();
}

void DTS6012M_StopLaser()
{
    Wire.beginTransmission(DTS6012M_ADD);
    Wire.write(LASER_EN_ADD);
    Wire.write(0x00); // Stop laser
    Wire.endTransmission();
}

float DTS6012M_GetDistance(DTS6012M* dev)
{
    Wire.beginTransmission(DTS6012M_ADD);
    Wire.write(MSB_ADD); // request MSB first
    Wire.endTransmission();

    Wire.requestFrom(DTS6012M_ADD, 2); // read 2 bytes
    if(Wire.available() >= 2) {
        uint8_t msb = Wire.read();
        uint8_t lsb = Wire.read();
        dev->raw_distance = (msb << 8) | lsb;
        return dev->raw_distance * DTS6012M_SCALING_FACTOR + DTS6012M_OFFSET_DISTANCE;
    }
    return -1; // error
}
