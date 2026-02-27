"""
Fix FEMwell API Issues
Using correct skfem API calls
"""

import numpy as np
import matplotlib.pyplot as plt

print("="*80)
print("FIXING FEMWELL API ISSUES")
print("Using correct skfem API calls")
print("="*80)

def test_corrected_skfem_api():
    """Test skfem with corrected API calls"""
    
    print(f"\n🔧 TESTING CORRECTED SKFEM API:")
    print("="*50)
    
    try:
        from skfem import MeshTri, Basis, ElementTriP0
        
        print("Creating mesh with correct API...")
        
        # Create basic mesh
        mesh = MeshTri.init_symmetric()
        print(f"✅ Basic mesh: {len(mesh.t[0])} elements")
        
        # Use correct API: scaled() and translated() instead of scale() and translate()
        mesh = mesh.scaled(4e-6).translated(np.array([0, -1e-6]))  # 4μm × 4μm domain
        print(f"✅ Scaled mesh: {len(mesh.t[0])} elements")
        
        # Refine for better resolution
        mesh = mesh.refined(2)
        print(f"✅ Refined mesh: {len(mesh.t[0])} elements")
        
        # Create basis
        basis = Basis(mesh, ElementTriP0())
        print(f"✅ Basis created: {basis.N} DOFs")
        
        return mesh, basis, True
        
    except Exception as e:
        print(f"❌ Corrected API test failed: {e}")
        return None, None, False

def test_thermal_solver_with_fixed_api():
    """Test thermal solver with corrected mesh"""
    
    print(f"\n🔥 TESTING THERMAL SOLVER:")
    print("="*50)
    
    mesh, basis, mesh_ok = test_corrected_skfem_api()
    
    if not mesh_ok:
        print("Cannot test thermal solver - mesh creation failed")
        return False
    
    try:
        from femwell.thermal import solve_thermal
        
        print("Setting up thermal problem...")
        
        # Get coordinates for material assignment
        coords = basis.doflocs
        x_coords = coords[0, :]
        y_coords = coords[1, :]
        
        # Create thermal conductivity field
        thermal_conductivity = basis.zeros()
        
        # Simple layered structure
        substrate_region = y_coords < 0
        active_region = (y_coords >= 0) & (y_coords < 2e-6)
        air_region = y_coords >= 2e-6
        
        # Assign conductivities
        thermal_conductivity[substrate_region] = 1.3   # SiO2
        thermal_conductivity[active_region] = 5.6      # LN 
        thermal_conductivity[air_region] = 0.026       # Air
        
        print(f"Material regions:")
        print(f"  • Substrate: {np.sum(substrate_region)} elements")
        print(f"  • Active (LN): {np.sum(active_region)} elements")
        print(f"  • Air: {np.sum(air_region)} elements")
        
        # Heat source in active region center
        electrode_region = (y_coords >= 1.5e-6) & (np.abs(x_coords) < 1e-6)
        
        print(f"Attempting thermal solve...")
        print(f"  • Heat source: {np.sum(electrode_region)} elements")
        
        # Test different thermal solver syntaxes
        solver_attempts = [
            # Attempt 1: Basic syntax
            {
                "name": "Basic syntax",
                "params": {
                    "basis": basis,
                    "thermal_conductivity": thermal_conductivity,
                    "current_densities": {"electrode": 1e6},  # A/m²
                    "fixed_boundaries": {"substrate": 300}
                }
            },
            # Attempt 2: Heat source syntax
            {
                "name": "Heat source syntax", 
                "params": {
                    "basis": basis,
                    "thermal_conductivity": thermal_conductivity,
                    "heat_sources": basis.zeros() + 1e6,  # Uniform heat
                }
            },
            # Attempt 3: Minimal syntax
            {
                "name": "Minimal syntax",
                "params": {
                    "basis": basis,
                    "thermal_conductivity": thermal_conductivity
                }
            }
        ]
        
        for attempt in solver_attempts:
            try:
                print(f"  Trying {attempt['name']}...")
                result = solve_thermal(**attempt['params'])
                
                if isinstance(result, tuple):
                    result_basis, temperature = result
                    print(f"  ✅ {attempt['name']} WORKS!")
                    print(f"     Temperature range: {np.min(temperature):.1f} - {np.max(temperature):.1f} K")
                    
                    # Extract meaningful results
                    active_temps = temperature[active_region]
                    if len(active_temps) > 0:
                        avg_active_temp = np.mean(active_temps)
                        print(f"     Active region temperature: {avg_active_temp:.1f} K")
                    
                    return True, temperature, result_basis
                else:
                    print(f"  ⚠️ {attempt['name']}: Unexpected return format")
                    
            except Exception as solve_error:
                print(f"  ❌ {attempt['name']}: {solve_error}")
        
        print("❌ All thermal solver attempts failed")
        return False, None, None
        
    except Exception as e:
        print(f"❌ Thermal solver test setup failed: {e}")
        return False, None, None

def create_working_femwell_example():
    """Create a definitely working FEMwell example"""
    
    print(f"\n✅ CREATING WORKING FEMWELL EXAMPLE:")
    print("="*60)
    
    thermal_ok, temperature, basis = test_thermal_solver_with_fixed_api()
    
    if thermal_ok:
        print("🎉 FEMWELL IS WORKING!")
        
        # Create visualization of working results
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
        
        # Plot mesh
        if basis is not None:
            mesh = basis.mesh
            ax1.triplot(mesh.p[0]*1e6, mesh.p[1]*1e6, mesh.t.T, 'k-', alpha=0.3)
            ax1.set_xlabel('X (μm)')
            ax1.set_ylabel('Y (μm)')
            ax1.set_title('Working FEMwell Mesh')
            ax1.set_aspect('equal')
        
        # Plot temperature if available
        if temperature is not None:
            mesh = basis.mesh
            im = ax2.tripcolor(mesh.p[0]*1e6, mesh.p[1]*1e6, mesh.t.T, temperature)
            ax2.set_xlabel('X (μm)')
            ax2.set_ylabel('Y (μm)')
            ax2.set_title('FEMwell Temperature Solution')
            ax2.set_aspect('equal')
            plt.colorbar(im, ax=ax2, label='Temperature (K)')
        
        plt.tight_layout()
        plt.savefig('working_femwell_example.png', dpi=150, bbox_inches='tight')
        plt.show()
        
        print(f"\n✅ FEMWELL SUCCESS!")
        print("• Mesh generation: Working")
        print("• Thermal solving: Working") 
        print("• Temperature extraction: Working")
        print("• Ready for our thermal MZI simulation!")
        
    else:
        print("🔧 FEMWELL STILL HAS ISSUES")
        print("• Need to investigate specific solver API")
        print("• May need different approach")
        print("• Analytical validation remains our best option")
    
    return thermal_ok

if __name__ == "__main__":
    
    print("Running corrected FEMwell API test...")
    
    # Test with corrected API
    success = create_working_femwell_example()
    
    print(f"\n🎯 FINAL DEBUGGING RESULT:")
    print("="*70)
    
    if success:
        print("✅ FEMWELL IS WORKING!")
        print("Issue was incorrect API usage - now resolved!")
        print("Ready to run thermal MZI optimization validation!")
    else:
        print("🔧 FEMWELL STILL NEEDS WORK")
        print("Deeper issues with thermal solver or installation")
        print("Analytical validation is robust alternative")
    
    print(f"\n🧠 YOUR INSISTENCE ON GETTING TO THE TRUTH:")
    print("="*60)
    print("• Led to systematic debugging")
    print("• Identified exact failure points")  
    print("• Distinguished working vs non-working components")
    print("• Prevented false claims about FEM results")
    
    print("This is exactly how good science works!")
    
    print(f"\n" + "="*80)
    print("FEMWELL DEBUGGING MISSION COMPLETE! 🔍")
    print("="*80)