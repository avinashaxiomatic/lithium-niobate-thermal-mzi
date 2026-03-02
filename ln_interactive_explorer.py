import marimo

__generated_with = "0.20.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import sys
    import warnings
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    sys.path.insert(0, "/home/kumar/femwell/repo")
    sys.path.insert(0, "/home/kumar/femwell")

    from ln_mzi_simulation import (
        T_AMB, W_SIM, H_LN, H_SLAB, W_WG,
        K_SIO2, K_AL, K_LN_X, K_LN_Y,
        N_LN, N_SIO2, DN_DT_LN, DN_DT_SIO2,
        R_TOTAL, SIGMA_AL, WAVELENGTH, DELTA_L, N_GROUP,
        solve_thermal_2p5d, compute_alpha_eff,
    )
    from ln_optimization_sweeps import (
        build_vertical_geometry_param, build_suspended_geometry,
        build_mesh_sweep, run_single_voltage_solve,
        setup_thermal_conductivity_ext, compute_constrained_metrics,
        K_AIR, N_AIR, T_MAX_LIMIT,
    )
    from skfem import Basis, ElementTriP0

    warnings.filterwarnings("ignore", category=FutureWarning)
    warnings.filterwarnings("ignore", message=".*SparseEfficiencyWarning.*")

    alpha_eff = compute_alpha_eff()
    return (
        Basis,
        ElementTriP0,
        K_AIR,
        N_AIR,
        R_TOTAL,
        SIGMA_AL,
        T_AMB,
        T_MAX_LIMIT,
        alpha_eff,
        build_mesh_sweep,
        build_suspended_geometry,
        build_vertical_geometry_param,
        compute_constrained_metrics,
        mo,
        np,
        plt,
        run_single_voltage_solve,
        setup_thermal_conductivity_ext,
        solve_thermal_2p5d,
    )


@app.cell
def _(mo):
    mo.md(r"""
    # LN MZI Thermo-Optic Phase Shifter — Interactive Explorer

    **What this is:** An interactive design tool for a lithium niobate (LN)
    Mach-Zehnder interferometer thermo-optic phase shifter, based on
    [Chen et al., IEEE PTL 2021](https://doi.org/10.1109/LPT.2021.3070375).

    **The optimization story:**

    1. **Paper baseline** — vertical heater (w=3 μm) with 1 μm isolation → ~1.3 pm/mW
    2. **Electrode optimization** — narrower heater (1.5 μm) + thinner isolation (0.5 μm) → ~2.5 pm/mW
    3. **Thick BOX** — increased thermal resistance to substrate (4 μm BOX) → ~3.5 pm/mW
    4. **Suspended design** — HF undercut removes SiO2 beneath waveguide → **~13 pm/mW (10× improvement!)**

    **Coffee cup analogy:** Think of the waveguide as a cup of coffee you want to keep hot.
    The substrate is a cold metal table (heat sink). The BOX oxide is a coaster.
    Making the coaster thicker (thick BOX) helps a bit. But cutting away the table entirely
    underneath (suspended/undercut) is far more effective — your coffee now sits on an
    air bridge with almost no conduction path to the cold surface.

    **How to use:** Pick a preset below to see known configurations, or select "Custom"
    and adjust sliders to explore the parameter space. Each solve takes ~5-8 seconds.
    """)
    return


@app.cell
def _(mo):
    preset = mo.ui.dropdown(
        options={
            "Paper baseline (w_al=3, h_iso=1, no undercut)": "baseline",
            "Optimized electrode (w_al=1.5, h_iso=0.5)": "electrode",
            "Thick BOX (w_al=1.5, h_iso=0.5, h_box=4)": "thick_box",
            "Suspended (w_uc=14, w_al=1.5, h_iso=0.5)": "suspended",
            "Custom (use sliders)": "custom",
        },
        value="Paper baseline (w_al=3, h_iso=1, no undercut)",
        label="Design preset",
    )
    mo.md(f"### Design Preset\n{preset}")
    return (preset,)


@app.cell
def _(mo, preset):
    _presets = {
        "baseline":  {"h_iso": 1.0, "w_al": 3.0, "w_uc": 0,  "h_sub": 2.0, "volt": 10.0},
        "electrode": {"h_iso": 0.5, "w_al": 1.5, "w_uc": 0,  "h_sub": 2.0, "volt": 10.0},
        "thick_box": {"h_iso": 0.5, "w_al": 1.5, "w_uc": 0,  "h_sub": 4.0, "volt": 10.0},
        "suspended": {"h_iso": 0.5, "w_al": 1.5, "w_uc": 14, "h_sub": 2.0, "volt": 10.0},
        "custom":    {"h_iso": 1.0, "w_al": 3.0, "w_uc": 0,  "h_sub": 2.0, "volt": 10.0},
    }
    _p = _presets.get(preset.value, _presets["baseline"])
    _is_custom = preset.value == "custom"

    sl_h_iso = mo.ui.slider(
        start=0.3, stop=2.0, step=0.1,
        value=_p["h_iso"],
        label="h_isolation (μm)",
        disabled=not _is_custom,
    )
    sl_w_al = mo.ui.slider(
        start=1.0, stop=6.0, step=0.5,
        value=_p["w_al"],
        label="w_electrode (μm)",
        disabled=not _is_custom,
    )
    sl_w_uc = mo.ui.slider(
        start=0, stop=14, step=1,
        value=_p["w_uc"],
        label="w_undercut (μm)",
        disabled=not _is_custom,
    )
    sl_h_sub = mo.ui.slider(
        start=1.0, stop=4.0, step=0.5,
        value=_p["h_sub"],
        label="h_substrate (μm)",
        disabled=not _is_custom,
    )
    sl_volt = mo.ui.slider(
        start=1.0, stop=15.0, step=0.5,
        value=_p["volt"],
        label="Voltage (V)",
        disabled=not _is_custom,
    )
    return sl_h_iso, sl_h_sub, sl_volt, sl_w_al, sl_w_uc


@app.cell
def _(mo, preset, sl_h_iso, sl_h_sub, sl_volt, sl_w_al, sl_w_uc):
    _is_custom = preset.value == "custom"
    mo.md(
        f"""
        ### Parameters {"(adjust sliders)" if _is_custom else "(locked to preset — select Custom to unlock)"}

        | Parameter | Range | Control | Value |
        |-----------|-------|---------|-------|
        | Isolation thickness | 0.3–2.0 μm | {sl_h_iso} | **{sl_h_iso.value:.1f} μm** |
        | Electrode width | 1.0–6.0 μm | {sl_w_al} | **{sl_w_al.value:.1f} μm** |
        | Undercut width | 0–14 μm | {sl_w_uc} | **{sl_w_uc.value:.0f} μm** |
        | BOX thickness | 1.0–4.0 μm | {sl_h_sub} | **{sl_h_sub.value:.1f} μm** |
        | Applied voltage | 1.0–15.0 V | {sl_volt} | **{sl_volt.value:.1f} V** |
        """
    )
    return


@app.cell
def _(
    K_AIR,
    N_AIR,
    alpha_eff,
    build_mesh_sweep,
    build_suspended_geometry,
    build_vertical_geometry_param,
    compute_constrained_metrics,
    mo,
    run_single_voltage_solve,
    sl_h_iso,
    sl_h_sub,
    sl_volt,
    sl_w_al,
    sl_w_uc,
):
    mo.status.spinner(title="Running FEM solve...")

    _h_iso = sl_h_iso.value
    _w_al = sl_w_al.value
    _w_uc = sl_w_uc.value
    _h_sub = sl_h_sub.value
    _voltage = sl_volt.value

    # Build geometry
    if _w_uc > 0:
        polygons = build_suspended_geometry(
            w_undercut=_w_uc,
            h_isolation=_h_iso,
            w_al=_w_al,
            h_substrate=_h_sub,
        )
        extra_k = {
            "undercut": (K_AIR, K_AIR),
            "trench_left": (K_AIR, K_AIR),
            "trench_right": (K_AIR, K_AIR),
        }
        extra_eps = {
            "undercut": (N_AIR, 0.0),
            "trench_left": (N_AIR, 0.0),
            "trench_right": (N_AIR, 0.0),
        }
    else:
        polygons = build_vertical_geometry_param(
            h_isolation=_h_iso,
            w_al=_w_al,
            h_substrate=_h_sub,
        )
        extra_k = None
        extra_eps = None

    mesh = build_mesh_sweep(polygons, label="interactive")

    results = run_single_voltage_solve(
        polygons, mesh, alpha_eff, V=_voltage,
        extra_domains_k=extra_k, extra_domains_eps=extra_eps,
    )
    results = compute_constrained_metrics(results, V_sim=_voltage)
    results["voltage"] = _voltage
    results["h_isolation"] = _h_iso
    results["w_al"] = _w_al
    results["w_undercut"] = _w_uc
    results["h_substrate"] = _h_sub
    return extra_k, mesh, polygons, results


@app.cell
def _(R_TOTAL, T_MAX_LIMIT, mo, results):
    _eta = results["tuning_eff_pm_per_mW"]
    _dT = results["dT_core"]
    _T_max = results["T_max"]
    _shift = results["delta_lambda_nm"]
    _P_mW = results["power_mW"]
    _V = results["voltage"]

    # Baseline comparison (paper: ~1.32 pm/mW at 10V)
    _baseline_eta = 1.32
    _improvement = (_eta / _baseline_eta - 1) * 100

    # Thermal constraint
    _within_budget = _T_max <= T_MAX_LIMIT
    _status_color = "green" if _within_budget else "red"
    _status_text = "WITHIN budget" if _within_budget else "EXCEEDS limit"

    _V_max = results.get("V_max", _V)
    _P_max_mW = results.get("P_max_mW", _P_mW)
    _shift_max = results.get("delta_lambda_max_nm", _shift)

    # Power needed for 1 nm shift (if shift > 0)
    _P_for_1nm = _P_mW / _shift if _shift > 0 else float("inf")
    _baseline_P_for_1nm = 1000.0 / _baseline_eta  # mW for 1 nm at baseline
    _power_saving = _baseline_P_for_1nm - _P_for_1nm

    mo.md(
        f"""
        ### Results Dashboard

        | Metric | Value |
        |--------|-------|
        | **Tuning efficiency** | **{_eta:.2f} pm/mW** |
        | Core ΔT | {_dT:.1f} K |
        | Peak T_max | {_T_max:.0f} K |
        | Wavelength shift at {_V:.1f} V | {_shift:.3f} nm |
        | Power at {_V:.1f} V | {_P_mW:.1f} mW (R={R_TOTAL:.0f} Ω) |

        **Thermal constraint (T_max ≤ {T_MAX_LIMIT:.0f} K):**
        <span style="color:{_status_color};font-weight:bold">{_status_text}</span>
        — Max safe voltage: {_V_max:.1f} V, max power: {_P_max_mW:.0f} mW,
        max shift at limit: {_shift_max:.3f} nm

        **vs. paper baseline ({_baseline_eta} pm/mW):**
        {"📈" if _improvement > 0 else "📉"} {abs(_improvement):.0f}% {"more" if _improvement > 0 else "less"} efficient
        | Power for 1 nm shift: {_P_for_1nm:.0f} mW (baseline: {_baseline_P_for_1nm:.0f} mW, saving {_power_saving:.0f} mW)
        """
    )
    return


@app.cell
def _(
    Basis,
    ElementTriP0,
    R_TOTAL,
    SIGMA_AL,
    T_AMB,
    alpha_eff,
    extra_k,
    mesh,
    np,
    plt,
    polygons,
    results,
    setup_thermal_conductivity_ext,
    solve_thermal_2p5d,
):
    # Re-solve to get the temperature field for plotting
    _basis0 = Basis(mesh, ElementTriP0(), intorder=4)
    _kxx, _kyy = setup_thermal_conductivity_ext(_basis0, extra_k)

    _V = results["voltage"]
    _I = _V / R_TOTAL
    _A_heater = polygons["heater"].area
    _J = _I / _A_heater

    _basis_t, _temp = solve_thermal_2p5d(
        _basis0, _kxx, _kyy, alpha_eff,
        specific_conductivity={"heater": SIGMA_AL},
        current_densities={"heater": _J},
        fixed_boundaries={"bottom": T_AMB},
    )

    # Project to P0 for plotting
    _temp_p0 = _basis0.project(_basis_t.interpolate(_temp))

    fig1, ax1 = plt.subplots(figsize=(10, 5))
    # Use P1 temp (per-node) with gouraud shading for smooth plot
    _tri = ax1.tripcolor(
        _basis_t.mesh.p[0], _basis_t.mesh.p[1],
        _basis_t.mesh.t.T, _temp - T_AMB,
        shading="gouraud",
    )
    plt.colorbar(_tri, ax=ax1, label="ΔT (K)")

    # Annotate layer boundaries
    _h_sub = results["h_substrate"]
    _y_box_top = _h_sub
    _y_ln_top = _y_box_top + 0.7  # H_LN
    ax1.axhline(_y_box_top, color="white", linestyle="--", linewidth=0.8, alpha=0.7)
    ax1.axhline(_y_ln_top, color="white", linestyle="--", linewidth=0.8, alpha=0.7)
    ax1.text(-7.5, _y_box_top + 0.05, "BOX top", color="white", fontsize=8)
    ax1.text(-7.5, _y_ln_top + 0.05, "LN top", color="white", fontsize=8)

    ax1.set_xlabel("x (μm)")
    ax1.set_ylabel("y (μm)")
    ax1.set_title(f"Temperature Rise (ΔT) — V={_V:.1f}V, Core ΔT={results['dT_core']:.1f}K")
    ax1.set_aspect("equal")

    # Store data for vertical profile plot
    _mesh_coords = _basis_t.mesh.p  # 2 x N_nodes
    _x_coords = _mesh_coords[0, :]
    _y_coords = _mesh_coords[1, :]

    # Extract vertical profile at x≈0
    _x_tol = 0.15
    _center_mask = np.abs(_x_coords) < _x_tol
    _y_center = _y_coords[_center_mask]
    _T_center = _temp[_center_mask]
    _sort_idx = np.argsort(_y_center)
    y_profile = _y_center[_sort_idx]
    T_profile = _T_center[_sort_idx]

    fig1
    return T_profile, y_profile


@app.cell
def _(T_AMB, T_profile, plt, results, y_profile):
    _h_sub = results["h_substrate"]
    _y_box_top = _h_sub
    _y_ln_top = _y_box_top + 0.7

    fig2, ax2 = plt.subplots(figsize=(7, 5))
    ax2.plot(T_profile - T_AMB, y_profile, "b-", linewidth=2)

    # Shade BOX region
    ax2.axhspan(0, _y_box_top, alpha=0.15, color="blue", label="SiO₂ BOX")
    # Shade LN region
    ax2.axhspan(_y_box_top, _y_ln_top, alpha=0.15, color="orange", label="LN")

    ax2.set_xlabel("ΔT (K)")
    ax2.set_ylabel("y (μm)")
    ax2.set_title("Vertical Temperature Profile at x = 0")
    ax2.legend(loc="upper right")
    ax2.grid(True, alpha=0.3)

    # Mark core ΔT
    _y_core = _y_box_top + 0.3 + 0.2  # slab + half etch
    _dT_core = results["dT_core"]
    ax2.axhline(_y_core, color="red", linestyle=":", alpha=0.5)
    ax2.annotate(
        f"Core ΔT ≈ {_dT_core:.1f} K",
        xy=(_dT_core, _y_core),
        xytext=(_dT_core * 0.5, _y_core + 0.3),
        fontsize=9, color="red",
        arrowprops=dict(arrowstyle="->", color="red", alpha=0.7),
    )

    # Mark undercut region if present
    _w_uc = results["w_undercut"]
    if _w_uc > 0:
        _y_uc_top = _y_box_top
        _y_uc_bot = max(0.05, 0)
        ax2.axhspan(_y_uc_bot, _y_uc_top, alpha=0.1, color="green",
                     label=f"Undercut (air, w={_w_uc} μm)")
        ax2.legend(loc="upper right")

    fig2
    return


@app.cell
def _(mo):
    mo.md(r"""
    ### Optimization Progression — Reference Table

    Pre-computed results from full parameter sweeps (not reactive to sliders).
    Shows the journey from paper baseline to 10× efficiency improvement.

    | Design | η (pm/mW) | V_max (V) | P_max (mW) | Δλ_max (nm) | Key change |
    |--------|-----------|-----------|------------|-------------|------------|
    | **Paper baseline** | 1.32 | 10.0 | 1000 | 1.21 | w_al=3, h_iso=1, h_box=2 |
    | **Optimized electrode** | 2.50 | 8.2 | 672 | 1.68 | w_al=1.5, h_iso=0.5 |
    | **Thick BOX** | 3.53 | 7.0 | 490 | 1.73 | + h_box=4 μm |
    | **Suspended (w_uc=14)** | 13.2 | 3.6 | 130 | 1.71 | + full undercut |

    **Key insight:** The suspended design achieves ~10× the baseline efficiency.
    It needs only ~130 mW to reach the thermal limit, vs 1000 mW for the baseline.
    The maximum wavelength shift is similar across designs (~1.7 nm) because
    more efficient designs hit the thermal ceiling at lower power.

    **Design trade-offs:**
    - Higher efficiency → lower thermal budget (T_max reached sooner)
    - Suspended structures are mechanically fragile
    - Thinner isolation risks optical loss from heater proximity
    - Narrower electrodes have higher current density → reliability concerns
    """)
    return


if __name__ == "__main__":
    app.run()
