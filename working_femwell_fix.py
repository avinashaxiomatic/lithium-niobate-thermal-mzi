"""
Working FEMwell Fix - Using Correct API
Based on debugging the mesh_from_OrderedDict parameters
"""

print("="*80)
print("WORKING FEMWELL FIX")
print("="*80)

def test_correct_femwell_api():
    """Test with correct mesh_from_OrderedDict API"""
    
    print(f"\n🔧 TESTING CORRECT FEMWELL API:")
    print("="*50)
    
    try:
        from femwell.mesh import mesh_from_OrderedDict
        from femwell.thermal import solve_thermal
        from skfem import Basis, ElementTriP0
        from skfem.io import from_meshio
        from collections import OrderedDict
        from shapely.geometry import Polygon, LineString
        
        print("✅ All imports successful")
        
        # Create minimal geometry
        simple_polygons = OrderedDict()
        
        simple_polygons["substrate"] = Polygon([
            (-2, -1),  # Using simple coordinates (μm)
            (-2, 0),
            (2, 0), 
            (2, -1),
        ])
        
        simple_polygons["heater"] = Polygon([
            (-1, 1),
            (-1, 1.5),
            (1, 1.5),
            (1, 1),
        ])
        
        # CRITICAL: Provide resolutions parameter (this was missing!)
        resolutions = {
            "substrate": {"resolution": 0.3, "distance": 1},
            "heater": {"resolution": 0.1, "distance": 1},
        }
        
        print("Creating mesh with correct API...")
        print(f"  • Polygons: {len(simple_polygons)}")
        print(f"  • Resolutions: {len(resolutions)}")
        
        # Call with correct parameters
        mesh = mesh_from_OrderedDict(
            simple_polygons, 
            resolutions=resolutions,  # This was missing!
            default_resolution_max=0.5
        )
        
        print("✅ MESH CREATION SUCCESS!")
        print(f"   Mesh type: {type(mesh)}")
        
        # Convert to skfem mesh
        skfem_mesh = from_meshio(mesh)
        print(f"✅ Converted to skfem: {len(skfem_mesh.t[0])} elements")
        
        # Create basis
        basis0 = Basis(skfem_mesh, ElementTriP0())
        print(f"✅ Basis created: {basis0.N} DOFs")
        
        # Check subdomains
        if hasattr(skfem_mesh, 'subdomains'):
            print(f"   Subdomains: {skfem_mesh.subdomains}")
            if skfem_mesh.subdomains is not None:
                print(f"   Available domains: {list(skfem_mesh.subdomains.keys())}")
        
        # Set up thermal properties
        thermal_conductivity = basis0.zeros()
        
        # Assign thermal conductivities
        for domain, k_value in {"substrate": 1.3, "heater": 200}.items():
            try:
                dofs = basis0.get_dofs(elements=domain)
                thermal_conductivity[dofs] = k_value
                print(f"  ✅ {domain}: {k_value} W/(m·K) ({len(dofs)} elements)")
            except Exception as e:
                print(f"  ❌ {domain}: {e}")
        
        # Test thermal solve
        print("Testing thermal solve...")
        
        try:
            basis_result, temperature = solve_thermal(
                basis0,
                thermal_conductivity,
                specific_conductivity={"heater": 1e6},
                current_densities={"heater": 1e6},
                fixed_boundaries={"substrate": 300},
            )
            
            print("🎉 FEMWELL THERMAL SOLVE SUCCESS!")
            print(f"   Temperature range: {np.min(temperature):.1f} - {np.max(temperature):.1f} K")
            
            return True, temperature, basis_result
            
        except Exception as solve_error:
            print(f"❌ Thermal solve error: {solve_error}")
            print("But mesh creation worked! Progress!")
            return False, None, None
    
    except Exception as api_error:
        print(f"❌ API error: {api_error}")
        import traceback
        traceback.print_exc()
        return False, None, None

def run_official_example():
    """Try to run the official FEMwell example"""
    
    print(f"\n📚 RUNNING OFFICIAL FEMWELL EXAMPLE:")
    print("="*60)
    
    # Let's try to extract and run just the thermal part of the official example
    
    try:
        # Use exact code from the working example file
        from collections import OrderedDict
        from shapely.geometry import LineString, Polygon
        from skfem import Basis, ElementTriP0
        from skfem.io import from_meshio
        from femwell.mesh import mesh_from_OrderedDict
        from femwell.thermal import solve_thermal
        
        print("Setting up exact working example geometry...")
        
        # EXACT geometry from working example
        w_sim = 8 * 2
        h_clad = 2.8
        h_box = 2
        w_core = 0.5
        h_core = 0.22
        h_heater = 0.14
        w_heater = 2
        offset_heater = 2 + (h_core + h_heater) / 2
        h_silicon = 0.5
        
        polygons = OrderedDict(
            bottom=LineString([
                (-w_sim / 2, -h_core / 2 - h_box - h_silicon),
                (w_sim / 2, -h_core / 2 - h_box - h_silicon),
            ]),
            core=Polygon([
                (-w_core / 2, -h_core / 2),
                (-w_core / 2, h_core / 2),
                (w_core / 2, h_core / 2),
                (w_core / 2, -h_core / 2),
            ]),
            heater=Polygon([
                (-w_heater / 2, -h_heater / 2 + offset_heater),
                (-w_heater / 2, h_heater / 2 + offset_heater),
                (w_heater / 2, h_heater / 2 + offset_heater),
                (w_heater / 2, -h_heater / 2 + offset_heater),
            ]),
            clad=Polygon([
                (-w_sim / 2, -h_core / 2),
                (-w_sim / 2, -h_core / 2 + h_clad),
                (w_sim / 2, -h_core / 2 + h_clad),
                (w_sim / 2, -h_core / 2),
            ]),
            box=Polygon([
                (-w_sim / 2, -h_core / 2),
                (-w_sim / 2, -h_core / 2 - h_box),
                (w_sim / 2, -h_core / 2 - h_box),
                (w_sim / 2, -h_core / 2),
            ]),
            wafer=Polygon([
                (-w_sim / 2, -h_core / 2 - h_box - h_silicon),
                (-w_sim / 2, -h_core / 2 - h_box),
                (w_sim / 2, -h_core / 2 - h_box),
                (w_sim / 2, -h_core / 2 - h_box - h_silicon),
            ]),
        )
        
        # EXACT resolutions from working example
        resolutions = {
            "core": {"resolution": 0.04, "distance": 1},
            "clad": {"resolution": 0.6, "distance": 1},
            "box": {"resolution": 0.6, "distance": 1},
            "heater": {"resolution": 0.1, "distance": 1},
        }
        
        print("Creating mesh with EXACT working example parameters...")
        
        # EXACT mesh creation from working example
        mesh = from_meshio(mesh_from_OrderedDict(polygons, resolutions, default_resolution_max=0.6))
        
        print("🎉 OFFICIAL EXAMPLE MESH SUCCESS!")
        print(f"   Mesh elements: {len(mesh.t[0])}")
        
        # EXACT thermal setup from working example
        basis0 = Basis(mesh, ElementTriP0(), intorder=4)
        thermal_conductivity_p0 = basis0.zeros()
        
        # EXACT thermal conductivities
        for domain, value in {
            "core": 90,
            "box": 1.38,
            "clad": 1.38,
            "heater": 28,
            "wafer": 148,
        }.items():
            thermal_conductivity_p0[basis0.get_dofs(elements=domain)] = value
        
        thermal_conductivity_p0 *= 1e-12  # EXACT unit conversion
        
        # EXACT thermal solve from working example
        current_density = 1e6  # Test current density
        
        basis, temperature = solve_thermal(
            basis0,
            thermal_conductivity_p0,
            specific_conductivity={"heater": 2.3e6},
            current_densities={"heater": current_density},
            fixed_boundaries={"bottom": 0},
        )
        
        print("🎉🎉 FEMWELL OFFICIAL EXAMPLE WORKS! 🎉🎉")
        print(f"Temperature solution: {np.min(temperature):.3f} - {np.max(temperature):.3f}")
        
        return True, temperature, basis
        
    except Exception as e:
        print(f"❌ Official example failed: {e}")
        import traceback
        traceback.print_exc()
        return False, None, None

if __name__ == "__main__":
    
    print("Testing official FEMwell example...")
    
    # Test corrected API first
    api_success, temp1, basis1 = test_correct_femwell_api()
    
    if not api_success:
        print("\nTrying official example...")
        official_success, temp2, basis2 = run_official_example()
        
        if official_success:
            print("\n✅ SUCCESS! Official FEMwell example works!")
            print("We can now adapt this for our LN thermal MZI")
        else:
            print("\n❌ Even official example fails")
            print("May be installation or environment issue")
    else:
        print("\n✅ SUCCESS! FEMwell API working!")
    
    success = api_success or (official_success if 'official_success' in locals() else False)
    
    print(f"\n🎯 FEMWELL STATUS:")
    print("="*50)
    
    if success:
        print("✅ FEMwell confirmed working!")
        print("✅ Can proceed with thermal MZI simulation!")
        print("✅ Your debugging persistence paid off!")
    else:
        print("🔧 FEMwell needs environment fixes")
        print("📊 Analytical validation remains robust")
        print("🔬 May need different FEM approach")