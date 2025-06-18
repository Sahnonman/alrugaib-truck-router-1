import streamlit as st
import requests
import folium
from streamlit_folium import st_folium

MAPBOX_TOKEN = st.secrets["MAPBOX_TOKEN"]

st.set_page_config(page_title="Alrugaib Routing", layout="wide")
st.title("Alrugaib Routing (Streamlit)")

with st.sidebar.form("input_form"):
    origin = st.text_input("عنوان الانطلاق", "الرياض، حي الملك فهد")
    destination = st.text_input("عنوان الوجهة", "جدة، المنطقة الصناعية")
    num_stops = st.number_input("عدد نقاط التوقف الوسيطة", 0, 5, 0)
    stops = [st.text_input(f"نقطة توقف {i+1}", key=f"stop_{i}") for i in range(num_stops)]
    fuel_price = st.number_input("سعر الوقود (ر.س./لتر)", 2.33)
    fuel_eff = st.number_input("كفاءة الوقود (كم/لتر)", 3.5)
    submitted = st.form_submit_button("احسب المسار")

def geocode(addr):
    url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{requests.utils.requote_uri(addr)}.json"
    res = requests.get(url, params={"access_token": MAPBOX_TOKEN, "limit": 1})
    res.raise_for_status()
    return res.json()["features"][0]["center"]

if submitted:
    try:
        origin_c = geocode(origin)
        dest_c = geocode(destination)
        stops_c = [geocode(s) for s in stops]
        coords = [origin_c] + stops_c + [dest_c]
        coord_str = ";".join(f"{lng},{lat}" for lng, lat in coords)
        url = f"https://api.mapbox.com/directions/v5/mapbox/driving/{coord_str}"
        resp = requests.get(url, params={"access_token": MAPBOX_TOKEN, "geometries": "geojson", "overview": "full"})
        resp.raise_for_status()
        data = resp.json()
        route = data["routes"][0]["geometry"]
        distance_km = data["routes"][0]["distance"] / 1000
        fuel_cost = distance_km / fuel_eff * fuel_price

        st.sidebar.markdown(f"**المسافة:** {distance_km:.1f} كم")
        st.sidebar.markdown(f"**تكلفة الوقود:** {fuel_cost:.2f} ر.س.")

        m = folium.Map(location=[origin_c[1], origin_c[0]], zoom_start=6)
        folium.GeoJson(route).add_to(m)
        for idx, (lng, lat) in enumerate(coords):
            folium.Marker([lat, lng], tooltip=["A"] + [str(i+1) for i in range(len(stops))] + ["B"][idx]).add_to(m)
        st_folium(m, width=700, height=500)
    except Exception as e:
        st.error(f"خطأ: {e}")
else:
    st.info("املأ البيانات في الشريط الجانبي ثم اضغط \"احسب المسار\"")
