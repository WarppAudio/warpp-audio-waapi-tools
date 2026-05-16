# 🎚️ Attenuation Batch Edit

🚀GUI tool allowing rapid editing of multiple attenuation curves at once within a Wwise project.

![image](https://github.com/user-attachments/assets/09f60713-ff65-4112-8044-409cbd58e61c)

## 📋 Interface Guide

<img width="1294" height="997" alt="image" src="https://github.com/user-attachments/assets/3d371921-6254-4733-9cdf-bebe812d138e" />


### 1. Get Attenuation!

* Fetches the selected attenuation curve.

### 2. Set Attenuation!

* Applies edited attenuation points  to all selected attenuations.
* Rescales normalized X-values (0–100) to the attenuation’s max distance.
  
### 3. Attenuation Type Selector

* Dropdown at top-left to choose which Wwise curve to edit (Volume, HPF, Spread, etc.).

### 4. Points Table (X % & Y columns)

Each row represents a control point with columns:

* **X %**: normalized horizontal position (0–100) with ± buttons for fine/coarse adjustments.
* **Y**: attenuation value with ± buttons.
* Values auto-validated and clamped.

> **Tip:** Large ± buttons adjust by 10 units; small ± adjust by 1 unit.


### 5. Curve Type Selectors (per point)

* Combo box in each row to choose the shape of each curve segment: Linear, Logarithmic, S-Curve, Exponential, etc.

### 6. Delete Point Buttons

* “Delete” button for each non-endpoint point/row.
* Endpoints (0% & 100%) cannot be removed.

### 7. Absolute Point Toggle (abs)

* Switches X between relative (%, scaled to the target attenuation's RadiusMax) and absolute (literal distance).

* Endpoints are always relative.

* When you click Set Attenuation!, target attenuations are skipped and shown in the conflict dialog if:
    - the copied absolute X value is greater than the target attenuation's RadiusMax
    - the copied absolute X value would land after one of the target's relative points

> **Tip:** Copy from the shortest attenuation to longer ones to avoid conflicts.

### 8. Curve Preview Plot

* Live  plot of the attenuation curve.

### 9. Project Name / Connection Status

* Displays the connected Wwise project name.

---


