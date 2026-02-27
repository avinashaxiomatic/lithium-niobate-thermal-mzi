# Minimal FEMwell Test for MCP
# Just test if basic thermal solving works

try:
    from femwell.thermal import solve_thermal
    from femwell.mesh import mesh_from_OrderedDict
    from skfem import Basis, ElementTriP0
    from skfem.io import from_meshio
    from collections import OrderedDict
    from shapely.geometry import Polygon
    import numpy as np
    
    print("✅ FEMwell imports successful")
    
    # Ultra-simple geometry
    polygons = OrderedDict()
    polygons["test_domain"] = Polygon([(-2, -1), (-2, 1), (2, 1), (2, -1)])
    
    # Simple mesh
    resolutions = {"test_domain": {"resolution": 0.5, "distance": 1}}
    mesh = from_meshio(mesh_from_OrderedDict(polygons, resolutions, default_resolution_max=1.0))
    
    print(f"✅ Mesh created: {len(mesh.t[0])} elements")
    
    # Basic thermal solve
    basis0 = Basis(mesh, ElementTriP0())
    thermal_conductivity = basis0.zeros() + 100.0  # Uniform conductivity
    thermal_conductivity *= 1e-12  # FEMwell units
    
    basis, temperature = solve_thermal(
        basis0,
        thermal_conductivity, 
        specific_conductivity={},
        current_densities={},
        fixed_boundaries={},
    )
    
    print(f"🎉 MCP FEMWELL SUCCESS!")
    print(f"Temperature: {np.min(temperature):.2f} - {np.max(temperature):.2f} K")
    
    success = True
    temp_range = np.max(temperature) - np.min(temperature)
    
except Exception as e:
    print(f"❌ MCP FEMwell failed: {e}")
    success = False
    temp_range = 0

# Results
print(f"\nMCP Test Result: {'SUCCESS' if success else 'FAILED'}")
if success:
    print(f"Temperature range: {temp_range:.2f} K")
    print("✅ MCP FEMwell basic functionality confirmed!")
else:
    print("❌ MCP FEMwell has issues")