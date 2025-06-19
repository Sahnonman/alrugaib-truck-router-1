import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
import pandas as pd
import io
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ===== إعدادات Google Sheets =====
SHEET_NAME = "Alrugaib_Routing_Reports"
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
CREDS = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", SCOPE)
CLIENT = gspread.authorize(CREDS)
SHEET = CLIENT.open(SHEET_NAME).sheet1

# ===== المدن المتاحة =====
city_coords = {
    "الرياض": (24.7136, 46.6753),
    "جدة": (21.3891, 39.8579),
    "المدينة": (24.5247, 39.5692),
    "الدمام": (26.4207, 50.0888),
    "الاحساء": (25.3830, 49.5867),
    "القصيم": (26.2074, 43.4934),
    "تبوك": (28.3838, 36.5550),
    "خميس مشيط": (18.3083, 42.7294),
}

# ===== إعداد صفحة Streamlit =====
MAPBOX_TOKEN = st.secrets["MAPBOX_TOKEN"]
st.set_page_config(page_title="مسارات الشاحنات - الرقيب", layout="wide")
st.title("Alrugaib Truck Routing between Saudi Cities")

# ===== نموذج الإدخال =====
with st.sidebar.form("input_form"):
    origin = st.selectbox("مدينة الانطلاق", list(city_coords.keys()), index=0)
    destination = st.selectbox("مدينة الوجهة", list(city_coords.keys()), index=1)
    num_stops = st.number_input("عدد نقاط التوقف الوسيطة", 0, 5, 0)
    stops = [st.selectbox(f"نقطة توقف {i+1}", list(city_coords.keys()), key=f"stop_{i}") for i in range(num_stops)]

    vehicle_type = st.selectbox("نوع المركبة", ["ديانا", "تريلا"])
    payload = st.number_input("الحمولة (كجم)", 1000, 40000, step=1000)

    fuel_price = st.number_input("سعر الوقود (ر.س/لتر)", 1.66)
    fuel_eff = st.number_input("كفاءة الوقود (كم/لتر)", 3.2)

    cost_per_km_3pl = st.number_input("تكلفة 3PL (ر.س/كم)", 6.0)
    cost_per_km_fleet = st.number_input("تكلفة الأسطول الخاص (ر.س/كم)", 2.5)

    submitted = st.form_submit_button("احسب المسار")

# ===== معالجة الإحداثيات =====
def get_coords(city_name):
    lat, lon = city_coords[city_name]
    return (lon, lat)

# ===== إذا تم الضغط على "احسب المسار" =====
if submitted:
    try:
        origin_c = get_coords(origin)
        dest_c = get_coords(destination)
        stops_c = [get_coords(s) for s in stops]
        coords = [origin_c] + stops_c + [dest_c]
        coord_str = ";".join(f"{lng},{lat}" for lng, lat in coords)

        # Mapbox Directions API
        url = f"https://api.mapbox.com/directions/v5/mapbox/driving/{coord_str}"
        resp = requests.get(url, params={"access_token": MAPBOX_TOKEN, "geometries": "geojson", "overview": "full"})
        resp.raise_for_status()
        data = resp.json()
        route = data["routes"][0]["geometry"]
        distance_km = data["routes"][0]["distance"] / 1000
        duration_min = data["routes"][0]["duration"] / 60
        eta = datetime.datetime.now() + datetime.timedelta(minutes=duration_min)

        fuel_cost = distance_km / fuel_eff * fuel_price
        total_cost_3pl = distance_km * cost_per_km_3pl
        total_cost_fleet = distance_km * cost_per_km_fleet

        # ===== التقرير =====
        report_data = {
            "من المدينة": origin,
            "إلى المدينة": destination,
            "نقاط التوقف": ", ".join(stops) if stops else "لا يوجد",
            "نوع المركبة": vehicle_type,
            "الحمولة (كجم)": payload,
            "المسافة (كم)": round(distance_km, 2),
            "مدة الرحلة (دقائق)": int(duration_min),
            "ETA وقت الوصول": eta.strftime("%Y-%m-%d %H:%M"),
            "تكلفة الوقود (ر.س)": round(fuel_cost, 2),
            "تكلفة 3PL (ر.س)": round(total_cost_3pl, 2),
            "تكلفة الأسطول الخاص (ر.س)": round(total_cost_fleet, 2)
        }

        df_report = pd.DataFrame([report_data])

        # ===== حفظ في Google Sheets =====
        SHEET.append_row(list(report_data.values()))

        # ===== تحميل Excel =====
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="xlsxwriter") as writer:
            df_report.to_excel(writer, index=False, sheet_name="Routing Report")
            writer.save()

        st.success("تم حساب المسار بنجاح وحفظ التقرير في Google Sheets ✅")

        st.download_button(
            label="📥 تحميل التقرير Excel",
            data=excel_buffer.getvalue(),
            file_name="routing_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # ===== الخريطة =====
        m = folium.Map(location=[origin_c[1], origin_c[0]], zoom_start=6)
        folium.GeoJson(route).add_to(m)

        labels = ["A"] + [str(i + 1) for i in range(len(stops))] + ["B"]
        for idx, (lng, lat) in enumerate(coords):
            folium.Marker([lat, lng], tooltip=labels[idx], popup=labels[idx]).add_to(m)

        st_folium(m, width=800, height=550)

    except Exception as e:
        st.error(f"حدث خطأ أثناء الحساب: {e}")

else:
    st.info("املأ الحقول واضغط 'احسب المسار' لحساب التكلفة وتصدير التقرير.")
