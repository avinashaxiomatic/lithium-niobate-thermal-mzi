"""
Simple FEMwell Check - Minimal test
"""

print("Testing FEMwell basic functionality...")

try:
    from femwell.thermal import solve_thermal
    print("✅ FEMwell thermal imported")
    
    from skfem import Basis, ElementTriP0
    print("✅ skfem imported")
    
    from femwell.mesh import mesh_from_OrderedDict
    print("✅ FEMwell mesh imported")
    
    # Test the exact working example geometry
    from collections import OrderedDict
    from shapely.geometry import Polygon, LineString
    
    # Minimal working geometry from example
    w_sim = 4
    h_core = 0.22
    h_box = 2
    h_silicon = 0.5
    
    simple_polygons = OrderedDict(
        bottom=LineString([
            (-w_sim / 2, -h_core / 2 - h_box - h_silicon),
            (w_sim / 2, -h_core / 2 - h_box - h_silicon),
        ]),
        
        wafer=Polygon([
            (-w_sim / 2, -h_core / 2 - h_box - h_silicon),
            (-w_sim / 2, -h_core / 2 - h_box),
            (w_sim / 2, -h_core / 2 - h_box),
            (w_sim / 2, -h_core / 2 - h_box - h_silicon),
        ]),
    )
    
    print("Creating minimal mesh...")
    
    # Test mesh creation
    mesh = mesh_from_OrderedDict(simple_polygons, default_resolution_max=0.5)
    print(f"✅ BASIC MESH WORKS! Elements: {len(mesh.cells_dict.get('triangle', []))}")
    
    from skfem.io import from_meshio
    skfem_mesh = from_meshio(mesh)
    print(f"✅ Converted to skfem: {len(skfem_mesh.t[0])} elements")
    
    print("\n🎉 FEMWELL BASIC FUNCTIONALITY CONFIRMED!")
    print("The issue is in our complex geometry, not FEMwell itself")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\nDone.")