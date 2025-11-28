from model import CityModel, TrafficLight, city_map

def test_traffic_light_sync():
    print("Testing Traffic Light Synchronization...")
    model = CityModel()
    
    # Find all traffic lights
    lights = [a for a in model.schedule.agents if isinstance(a, TrafficLight)]
    
    # Organize by position
    lights_by_pos = {(a.pos[0], a.pos[1]): a for a in lights}
    
    print(f"\nTotal Traffic Lights: {len(lights)}")
    print("\n=== Checking Synchronization ===")
    
    # Check each row for synchronized pairs
    sync_count = 0
    desync_count = 0
    
    for row in range(len(city_map)):
        row_lights = []
        for col in range(len(city_map[row])):
            if city_map[row][col] == 'S':
                x = col
                y = 23 - row
                if (x, y) in lights_by_pos:
                    light = lights_by_pos[(x, y)]
                    row_lights.append((col, light))
        
        # Check if consecutive lights in this row are synced
        if len(row_lights) > 1:
            for i in range(len(row_lights) - 1):
                col1, light1 = row_lights[i]
                col2, light2 = row_lights[i + 1]
                
                # Check if they are adjacent
                if col2 - col1 == 1:
                    if (light1.direction == light2.direction and 
                        light1.state == light2.state):
                        sync_count += 1
                        print(f"✅ Row {row}: S at col {col1} and {col2} are SYNCED ({light1.direction}, {light1.state})")
                    else:
                        desync_count += 1
                        print(f"❌ Row {row}: S at col {col1} and {col2} are DESYNCED")
                        print(f"   Col {col1}: {light1.direction}, {light1.state}, timer={light1.timer}")
                        print(f"   Col {col2}: {light2.direction}, {light2.state}, timer={light2.timer}")
    
    print(f"\n=== Summary ===")
    print(f"Synchronized pairs: {sync_count}")
    print(f"Desynchronized pairs: {desync_count}")
    
    if desync_count == 0:
        print("✅ ALL adjacent traffic lights are synchronized!")
    else:
        print("❌ Some traffic lights are not synchronized")
    
    # Check NS vs EW distribution
    ns_lights = [l for l in lights if l.direction == "NS"]
    ew_lights = [l for l in lights if l.direction == "EW"]
    
    print(f"\nDirection distribution:")
    print(f"  NS (North-South): {len(ns_lights)}")
    print(f"  EW (East-West): {len(ew_lights)}")
    
    # Check state distribution
    green_lights = [l for l in lights if l.state == "Green"]
    red_lights = [l for l in lights if l.state == "Red"]
    
    print(f"\nInitial state distribution:")
    print(f"  Green: {len(green_lights)}")
    print(f"  Red: {len(red_lights)}")

if __name__ == "__main__":
    test_traffic_light_sync()
