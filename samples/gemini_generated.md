# Hydraulic Pump Maintenance and Operating Guide

This document provides maintenance procedures, technical specifications, and safety guidelines for the Model-740 hydraulic pump subsystem.

---

## 1. Safety Instructions

**WARNING: HIGH PRESSURE FLUID HAZARD. Depressurize the system before you disconnect hydraulic lines.**

**CAUTION: Hot surfaces can cause burns. Let the pump cool for 30 minutes before you start maintenance.**

**NOTE:** Use only approved MIL-PRF-5606 hydraulic fluid.

---

## 2. System Description and Overview

The hydraulic pump supplies pressurized fluid to the primary flight control actuators. The assembly contains an electric motor, a rotary pump head, and an internal pressure relief valve. An integrated pressure sensor monitors system status in real time.

Operating parameters:
- Minimum operating pressure: 1500 psi
- Maximum operating pressure: 3000 psi
- Fluid capacity: 4.5 liters

The pump delivers consistent flow during peak operation. The electronic control unit regulates motor speed based on demand. All telemetry data is formatted in JSON and transmitted to the central avionics computer.

---

## 3. Maintenance Procedures

Follow these steps to replace the return line filter:

1. Put a collection container under the filter assembly.
2. Disconnect the electrical power connector from the pump.
3. Loosen the filter bowl with a standard wrench.
4. Remove the dirty filter element and the O-ring seal.
5. Clean the filter housing with an approved cleaning solvent.
6. Install a new filter element into the bowl.
7. Apply clean hydraulic fluid to the new O-ring.
8. Install the filter bowl and tighten to 25 Nm.
9. Connect the electrical power connector.
10. Bleed air from the system before operation.

---

## 4. Verification and Functional Check

After you replace the filter element, do a functional test:

1. Turn on the electrical power supply.
2. Start the hydraulic pump in low-pressure test mode.
3. Check the pressure gauge on the instrument panel.
4. Verify that the pressure reaches 3000 psi within 5 seconds.
5. Inspect all hose connections and fittings for leaks.
6. Record the test results in the maintenance log.

---

## 5. Technical Specifications and Parts List

| Item Number | Part Name | Specification | Replacement Interval |
|---|---|---|---|
| `HP-01` | Filter Element | 5-micron synthetic mesh | 500 operating hours |
| `HP-02` | O-ring Seal | Fluorocarbon elastomer | Replace at each service |
| `HP-03` | Pressure Sensor | 0–5000 psi range | On condition |
| `HP-04` | Relief Valve | Preset to 3200 psi | 2000 operating hours |

Refer to Section 6 and Figure 2 in the component manual for exploded assembly diagrams.

---

## 6. Troubleshooting Guidelines

When pump pressure is below 1500 psi, check these common causes:

- Air in the hydraulic lines: Bleed air from the high-pressure port.
- Low fluid level in the reservoir: Add approved fluid to the fill line.
- Clogged inlet strainer: Clean or replace the suction filter.
- Damaged drive coupling: Inspect the coupling teeth for wear.

To run diagnostic tests from the command line:

```bash
# Verify sensor communication
python -m stelint --format json docs/runbook.md

# Check telemetry feed
curl -s http://localhost:8080/api/telemetry | jq .
```

---

## 7. Compliance Checklist

- [x] Depressurize the system before maintenance.
- [x] Wear protective gloves and eye protection.
- [x] Dispose of used hydraulic fluid in accordance with environmental regulations.
- [x] Sign and date the aircraft maintenance record upon task completion.

