# 🎚️ Attenuation Batch Edit

🚀GUI tool allowing rapid editing of multiple attenuation curves at once within a Wwise project.

![image](https://github.com/user-attachments/assets/09f60713-ff65-4112-8044-409cbd58e61c)

## 📋 Interface Guide

![image](https://github.com/user-attachments/assets/59f4fae9-a621-40db-8464-0f614444f5d0)


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

### 7. Curve Preview Plot

* Live  plot of the attenuation curve.

### 8. Project Name / Connection Status

* Displays the connected Wwise project name.

---


