# game/airports/airport_detail.py

from game.utils.render import clear_screen

def view_airport_detail(game_state, airport):
    while True:
        clear_screen()

        # 🛫 Header Section
        print(f"🛫 {airport.get('name', 'Unknown Airport')} ({airport.get('iata', 'N/A')})")
        print(f"📍 {airport.get('city', 'Unknown City')}, {airport.get('country', 'Unknown Country')} 🇵🇭")
        print("=" * 50)
        print(f"📆 Opened: {airport.get('date_opened', 'N/A')}  |  Closed: {airport.get('date_closed', '-')}")
        print(f"🌏 Region: {airport.get('region', 'N/A')}  |  ✈️ Registration Prefix: {airport.get('aircraft_registration_prefix', 'N/A')}\n")

        # 🛠 Operational Stats Section
        print("📊 Operational Details")
        print("-" * 40)
        print(f"📏 Runway: {airport.get('runway_length_m', 0)} m ({airport.get('runways', 0)} Runways)")
        print(f"🅿️ Gates: {airport.get('total_pax_stands', 0)} Passenger | {airport.get('total_cargo_stands', 0)} Cargo")
        print(f"🕒 Avg. Taxi Time: {airport.get('avg_taxi_time_min', 'N/A')} min")
        print(f"✈️ Max Aircraft Class: {airport.get('max_aircraft_class', 'N/A')}")
        print(f"📦 Cargo Terminal: {'✅' if airport.get('has_cargo_terminal') else '❌'}\n")

        # 💵 Fees Section
        fees = airport.get('fees', {})
        print("💵 Airport Fees")
        print("-" * 40)
        print(f"💰 Base Landing Fee: ₱{fees.get('base_landing_fee', 0):,}")
        print(f"📏 MTOW Fee (per ton): ₱{fees.get('mtow_fee', 0):,}")
        print(f"🅿️ Parking Fee: ₱{fees.get('parking_fee', 0):,} / hr")
        print(f"🎫 Departure Fee per Pax: ₱{fees.get('departure_fee_per_pax', 0):,}\n")

        # 🏝️ City Info Section
        print("🏙️ City Insights")
        print("-" * 40)
        print(f"👥 Population: {airport.get('population', 0):,}")
        print(f"🌴 City Type: {', '.join(airport.get('city_type', ['N/A'])).title()}")
        print(f"⭐ Tourism Rating: {airport.get('tourism_rating', 'N/A')}/5")
        print(f"🏢 Business Activity: {airport.get('business_activity_level', 'N/A').title()}")
        print(f"👑 Luxury Travel Score: {airport.get('luxury_travel_score', 'N/A')}/5\n")

        # 🎉 Holidays & Seasons
        print("🎉 Key Holidays:")
        holidays = airport.get('holidays', [])
        if holidays:
            for h in holidays:
                print(f"• {h['name']} ({h['start_date']} – {h['end_date']}) +{int((h['demand_modifier'] - 1)*100)}% Demand")
        else:
            print("• None Listed")

        print("\n🍂 Seasonal Demand:")
        seasons = airport.get('seasonal_demand', {})
        print(f"❄️ Winter: {seasons.get('winter', 'N/A').title()}   🌸 Spring: {seasons.get('spring', 'N/A').title()}")
        print(f"☀️ Summer: {seasons.get('summer', 'N/A').title()}  🍁 Autumn: {seasons.get('autumn', 'N/A').title()}\n")

        # 📋 Action Menu
        print("[1] 🛂 Purchase Licenses")
        print("[2] 🕑 Buy Slots")
        print("[3] 📊 View Demand From This Airport")
        print("[0] ⬅ Back to Airports List")

        choice = input("\nEnter your choice: ").strip()

        if choice == "1":
            print("\n🚧 Purchase Licenses feature is coming soon!")
            input("Press Enter to return...")
        elif choice == "2":
            print("\n🚧 Buy Slots feature is coming soon!")
            input("Press Enter to return...")
        elif choice == "3":
            print("\n🚧 View Demand feature is coming soon!")
            input("Press Enter to return...")
        elif choice == "0":
            break
        else:
            print("❌ Invalid input. Please try again.")
            input("Press Enter to continue...")
