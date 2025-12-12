import streamlit as st
import pandas as pd
import paho.mqtt.client as mqtt
import json
from datetime import datetime
import time
import os
import plotly.express as px
import plotly.graph_objects as go
from collections import deque

# ========== Page Configuration ==========
st.set_page_config(
    page_title="Sistem Absensi Siswa",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ========== MQTT Configuration ==========
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
MQTT_TOPIC = "attendance/student"
MQTT_CLIENT_ID = "streamlit_dashboard"

# ========== Session State Initialization ==========
if 'mqtt_connected' not in st.session_state:
    st.session_state.mqtt_connected = False

if 'mqtt_messages' not in st.session_state:
    st.session_state.mqtt_messages = deque(maxlen=50)  # Keep last 50 messages

if 'last_update' not in st.session_state:
    st.session_state.last_update = datetime.now()

if 'mqtt_client' not in st.session_state:
    st.session_state.mqtt_client = None

# ========== MQTT Callbacks ==========
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        st.session_state.mqtt_connected = True
        client.subscribe(MQTT_TOPIC)
        print(f"[MQTT] Connected and subscribed to {MQTT_TOPIC}")
    else:
        st.session_state.mqtt_connected = False
        print(f"[MQTT] Connection failed: {rc}")

def on_disconnect(client, userdata, rc):
    st.session_state.mqtt_connected = False
    print("[MQTT] Disconnected")

def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode()
        data = json.loads(payload)
        
        # Add timestamp if not present
        if 'received_at' not in data:
            data['received_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Add to message queue
        st.session_state.mqtt_messages.appendleft(data)
        st.session_state.last_update = datetime.now()
        
        print(f"[MQTT] Received: {data}")
        
    except Exception as e:
        print(f"[MQTT] Error processing message: {e}")

# ========== MQTT Setup ==========
def setup_mqtt():
    if st.session_state.mqtt_client is None:
        try:
            client = mqtt.Client(client_id=MQTT_CLIENT_ID, clean_session=True)
            client.on_connect = on_connect
            client.on_disconnect = on_disconnect
            client.on_message = on_message
            
            client.connect(MQTT_BROKER, MQTT_PORT, 60)
            client.loop_start()
            
            st.session_state.mqtt_client = client
            print("[MQTT] Setup complete")
            
        except Exception as e:
            st.error(f"❌ MQTT Connection Error: {e}")
            st.session_state.mqtt_connected = False

# ========== Data Loading Functions ==========
@st.cache_data(ttl=5)
def load_attendance_csv():
    """Load attendance data from CSV file"""
    csv_file = 'Attendance.csv'
    
    if not os.path.exists(csv_file):
        # Create empty CSV if doesn't exist
        df = pd.DataFrame(columns=['Name', 'Time', 'Date'])
        df.to_csv(csv_file, index=False)
        return df
    
    try:
        df = pd.read_csv(csv_file, names=['Name', 'Time', 'Date'], skiprows=1)
        df = df.dropna()  # Remove empty rows
        
        # Clean whitespace
        df['Name'] = df['Name'].str.strip()
        df['Time'] = df['Time'].str.strip()
        df['Date'] = df['Date'].str.strip()
        
        return df
    except Exception as e:
        st.error(f"Error loading CSV: {e}")
        return pd.DataFrame(columns=['Name', 'Time', 'Date'])

# ========== Dashboard UI ==========
def main():
    # Setup MQTT
    setup_mqtt()
    
    # Title and Header
    st.title("📋 Sistem Absensi Siswa")
    st.markdown("---")
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Pengaturan")
        
        # MQTT Status
        if st.session_state.mqtt_connected:
            st.success("🟢 MQTT Connected")
        else:
            st.error("🔴 MQTT Disconnected")
        
        st.info(f"📡 Broker: {MQTT_BROKER}\n\n📢 Topic: {MQTT_TOPIC}")
        
        st.markdown("---")
        
        # Auto-refresh toggle
        auto_refresh = st.checkbox("🔄 Auto Refresh", value=True)
        
        if auto_refresh:
            refresh_interval = st.slider("Refresh Interval (detik)", 1, 10, 3)
        
        st.markdown("---")
        
        # Manual refresh button
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        
        st.markdown("---")
        st.caption(f"Last Update: {st.session_state.last_update.strftime('%H:%M:%S')}")
    
    # Main Content
    col1, col2, col3 = st.columns(3)
    
    # Load CSV data
    df = load_attendance_csv()
    
    # Statistics
    with col1:
        st.metric("👥 Total Siswa", len(df['Name'].unique()) if len(df) > 0 else 0)
    
    with col2:
        st.metric("✅ Total Absen Hari Ini", 
                  len(df[df['Date'] == datetime.now().strftime('%d-%B-%Y')]) if len(df) > 0 else 0)
    
    with col3:
        st.metric("📊 Total Records", len(df))
    
    st.markdown("---")
    
    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard", "📋 Histori Lengkap", "🔔 Live MQTT", "📈 Statistik"])
    
    # Tab 1: Dashboard
    with tab1:
        st.subheader("📊 Absensi Terbaru")
        
        if len(df) > 0:
            # Show last 10 records
            latest_df = df.tail(10).iloc[::-1]  # Reverse to show newest first
            
            st.dataframe(
                latest_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Name": st.column_config.TextColumn("Nama Siswa", width="medium"),
                    "Time": st.column_config.TextColumn("Waktu", width="medium"),
                    "Date": st.column_config.TextColumn("Tanggal", width="medium"),
                }
            )
        else:
            st.info("📭 Belum ada data absensi")
    
    # Tab 2: Full History
    with tab2:
        st.subheader("📋 Histori Absensi Lengkap")
        
        if len(df) > 0:
            # Search and filter
            col_search, col_filter = st.columns([2, 1])
            
            with col_search:
                search_name = st.text_input("🔍 Cari Nama Siswa", "")
            
            with col_filter:
                unique_dates = df['Date'].unique().tolist()
                selected_date = st.selectbox("📅 Filter Tanggal", ["Semua"] + unique_dates)
            
            # Apply filters
            filtered_df = df.copy()
            
            if search_name:
                filtered_df = filtered_df[filtered_df['Name'].str.contains(search_name, case=False)]
            
            if selected_date != "Semua":
                filtered_df = filtered_df[filtered_df['Date'] == selected_date]
            
            # Display filtered data
            st.dataframe(
                filtered_df.iloc[::-1],  # Newest first
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Name": st.column_config.TextColumn("Nama Siswa", width="medium"),
                    "Time": st.column_config.TextColumn("Waktu", width="medium"),
                    "Date": st.column_config.TextColumn("Tanggal", width="medium"),
                }
            )
            
            # Download button
            csv_data = filtered_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download CSV",
                data=csv_data,
                file_name=f"attendance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.info("📭 Belum ada data absensi")
    
    # Tab 3: Live MQTT
    with tab3:
        st.subheader("🔔 Live MQTT Messages")
        
        if st.session_state.mqtt_connected:
            st.success("✅ Menunggu data dari sistem absensi...")
            
            if len(st.session_state.mqtt_messages) > 0:
                for idx, msg in enumerate(st.session_state.mqtt_messages):
                    with st.container():
                        col_msg1, col_msg2 = st.columns([3, 1])
                        
                        with col_msg1:
                            st.markdown(f"""
                            **👤 {msg.get('name', 'Unknown').upper()}**  
                            ⏰ {msg.get('time', 'N/A')}  
                            📅 {msg.get('date', 'N/A')}
                            """)
                        
                        with col_msg2:
                            st.success("✅ Berhasil")
                        
                        st.markdown("---")
            else:
                st.info("📭 Belum ada pesan masuk")
        else:
            st.error("❌ MQTT belum terhubung. Sistem absensi offline.")
    
    # Tab 4: Statistics
    with tab4:
        st.subheader("📈 Statistik Absensi")
        
        if len(df) > 0:
            col_chart1, col_chart2 = st.columns(2)
            
            with col_chart1:
                # Attendance by student
                attendance_count = df['Name'].value_counts().reset_index()
                attendance_count.columns = ['Name', 'Count']
                
                fig1 = px.bar(
                    attendance_count,
                    x='Name',
                    y='Count',
                    title='Jumlah Absensi per Siswa',
                    labels={'Name': 'Nama Siswa', 'Count': 'Jumlah Absensi'},
                    color='Count',
                    color_continuous_scale='Blues'
                )
                fig1.update_layout(showlegend=False)
                st.plotly_chart(fig1, use_container_width=True)
            
            with col_chart2:
                # Attendance by date
                attendance_by_date = df['Date'].value_counts().reset_index()
                attendance_by_date.columns = ['Date', 'Count']
                attendance_by_date = attendance_by_date.sort_values('Date')
                
                fig2 = px.line(
                    attendance_by_date,
                    x='Date',
                    y='Count',
                    title='Tren Absensi per Tanggal',
                    labels={'Date': 'Tanggal', 'Count': 'Jumlah Absensi'},
                    markers=True
                )
                st.plotly_chart(fig2, use_container_width=True)
            
            # Top attendees
            st.markdown("### 🏆 Siswa Paling Rajin")
            top_students = df['Name'].value_counts().head(5).reset_index()
            top_students.columns = ['Nama', 'Jumlah Absensi']
            
            for idx, row in top_students.iterrows():
                col_rank, col_name, col_count = st.columns([1, 4, 2])
                with col_rank:
                    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
                    st.markdown(f"## {medals[idx]}")
                with col_name:
                    st.markdown(f"### {row['Nama'].upper()}")
                with col_count:
                    st.markdown(f"### {row['Jumlah Absensi']}x")
        else:
            st.info("📭 Belum ada data untuk ditampilkan")
    
    # Auto-refresh
    if auto_refresh:
        time.sleep(refresh_interval)
        st.rerun()

# ========== Run App ==========
if __name__ == "__main__":
    main()
