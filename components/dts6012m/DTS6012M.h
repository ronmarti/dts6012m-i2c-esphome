#pragma once
#ifndef INC_DTS6012M_H_
#define INC_DTS6012M_H_

#include <Wire.h>

/*
 * I2C Address defines
 */
#define DTS6012M_ADD 0x51 // DTS6012M default address (programmable)
#define MSB_ADD 0x00             // data MSB
#define LSB_ADD 0x01             // data LSB
#define LASER_EN_ADD 0x02        // Enable laser: 1 = start, 0 = stop

/*
 * Scaling factor to convert raw reading into distance in meters and offset amount
 */
#define DTS6012M_SCALING_FACTOR 0.001
#define DTS6012M_OFFSET_DISTANCE 0.0

/*
 * DTS6012M structure
 */
typedef struct
{
    uint16_t raw_distance;
} DTS6012M;

/*
 * Public function prototypes
 */
void DTS6012M_Init(DTS6012M* dev);
void DTS6012M_StartLaser();
void DTS6012M_StopLaser();
float DTS6012M_GetDistance(DTS6012M* dev);

#endif /* INC_DTS6012M_H_ */
