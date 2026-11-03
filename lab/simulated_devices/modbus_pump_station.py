import asyncio
import math
import random
import time

from pymodbus.datastore import (
    ModbusSequentialDataBlock,
    ModbusSlaveContext,
    ModbusServerContext,
)
from pymodbus.server import ModbusTcpServer


HOST = "0.0.0.0"
PORT = 5020

UPDATE_INTERVAL_SECONDS = 1.0


# Holding register addresses
MOTOR_TEMPERATURE = 0       # °C * 10
VIBRATION = 1               # mm/s * 100
RPM = 2                     # rpm
DISCHARGE_PRESSURE = 3      # bar * 100

# Coil addresses
RUNNING = 0


holding_registers = [
    650,    # 65.0 °C
    220,    # 2.20 mm/s
    1475,   # rpm
    480,    # 4.80 bar
]

coils = [True]


store = ModbusSlaveContext(
    hr=ModbusSequentialDataBlock(0, holding_registers + [0] * 20,),
    co=ModbusSequentialDataBlock(0, coils + [False] * 20,),
)

context = ModbusServerContext(
    slaves=store,
    single=True,
)


async def update_device():
    start_time = time.monotonic()

    running = True
    stopped_at = None

    while True:
        await asyncio.sleep(UPDATE_INTERVAL_SECONDS)

        elapsed = time.monotonic() - start_time

        # Occasionally stop/start the pump.
        if random.random() < 0.015:
            running = not running

            if not running:
                stopped_at = time.monotonic()
            else:
                stopped_at = None

        if running:
            rpm = int(
                1475
                + 25 * math.sin(elapsed / 8)
                + random.uniform(-8, 8)
            )

            temperature_c = (
                65
                + 4 * math.sin(elapsed / 25)
                + random.uniform(-0.3, 0.3)
            )

            vibration_mm_s = (
                2.2
                + 0.35 * math.sin(elapsed / 6)
                + random.uniform(-0.08, 0.08)
            )

            pressure_bar = (
                4.8
                + 0.3 * math.sin(elapsed / 10)
                + random.uniform(-0.05, 0.05)
            )

        else:
            rpm = 0

            stopped_seconds = (
                time.monotonic() - stopped_at
                if stopped_at is not None
                else 0
            )

            # Cool down gradually while stopped.
            temperature_c = max(
                30.0,
                65.0 - stopped_seconds * 0.15,
            )

            vibration_mm_s = random.uniform(0.0, 0.08)
            pressure_bar = random.uniform(0.0, 0.15)

        register_values = [
            int(round(temperature_c * 10)),
            int(round(vibration_mm_s * 100)),
            rpm,
            int(round(pressure_bar * 100)),
        ]

        # Function code 3 = holding registers.
        store.setValues(
            3,
            0,
            register_values,
        )

        # Function code 1 = coils.
        store.setValues(
            1,
            0,
            [running],
        )

        print(
            "[pump-plc-01] "
            f"running={running} "
            f"temperature={temperature_c:.1f}°C "
            f"vibration={vibration_mm_s:.2f}mm/s "
            f"rpm={rpm} "
            f"pressure={pressure_bar:.2f}bar"
        )


async def main():
    server = ModbusTcpServer(
        context=context,
        address=(HOST, PORT),
    )

    print(
        f"Simulated Modbus pump station running on "
        f"{HOST}:{PORT}"
    )

    await asyncio.gather(
        server.serve_forever(),
        update_device(),
    )


if __name__ == "__main__":
    asyncio.run(main())