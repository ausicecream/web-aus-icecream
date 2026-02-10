from flask import Flask, render_template, request, send_file, make_response, jsonify, redirect, url_for, send_from_directory
from io import BytesIO
from fpdf import FPDF
import sqlite3
import os
from datetime import datetime, timedelta
from collections import defaultdict
from flask import send_from_directory


app = Flask(__name__)

# Path database
DB_PATH = 'aus.db'
RESIT_PATH = 'resit'
os.makedirs(RESIT_PATH, exist_ok=True)

# Fungsi sambung DB
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Setup DB (jalan sekali je bila pertama kali)
def init_db():
    if not os.path.exists(DB_PATH):
        conn = get_db()
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS pesanan 
                     (bil_no INTEGER PRIMARY KEY AUTOINCREMENT, nama TEXT, tel_no TEXT, tarikh TEXT, alamat TEXT, 
                      package TEXT, qty INTEGER, total_price REAL, discount REAL, transport REAL, deposit REAL, balance REAL)''')
        c.execute('''CREATE TABLE IF NOT EXISTS stock_perisa 
                     (perisa TEXT PRIMARY KEY, in_qty INTEGER DEFAULT 0, out_qty INTEGER DEFAULT 0, balance INTEGER DEFAULT 0)''')
        c.execute('''CREATE TABLE IF NOT EXISTS stock_cone 
                     (cone TEXT PRIMARY KEY, in_qty INTEGER DEFAULT 0, out_qty INTEGER DEFAULT 0, balance INTEGER DEFAULT 0)''')

        # Default stock
        perisa_list = ['COKELAT', 'OREO', 'STRAWBAREY', 'JAGUNG', 'KELADI']
        cone_list = ['MINI', 'MEDIUM', 'DOUBLE']

        for p in perisa_list:
            c.execute("INSERT OR IGNORE INTO stock_perisa (perisa) VALUES (?)", (p,))
        for cone in cone_list:
            c.execute("INSERT OR IGNORE INTO stock_cone (cone) VALUES (?)", (cone,))

        conn.commit()
        conn.close()
        print("Database aus.db dicipta dan diinisialisasi.")

init_db()  # Jalankan sekali

@app.route('/')
def home():
    conn = get_db()
    c = conn.cursor()

    # Total hasil
    c.execute("SELECT SUM(total_price - discount + transport) FROM pesanan")
    total_hasil = c.fetchone()[0] or 0.0

    # Tempahan hari ini
    today = datetime.now().strftime('%Y-%m-%d')
    c.execute("SELECT COUNT(*) FROM pesanan WHERE tarikh LIKE ?", (f"%{today}%",))
    today_orders = c.fetchone()[0]

    # Stok rendah
    c.execute("SELECT perisa FROM stock_perisa WHERE balance < 2")
    stok_perisa_low = [row[0] for row in c.fetchall()]
    c.execute("SELECT cone FROM stock_cone WHERE balance < 2")
    stok_cone_low = [row[0] for row in c.fetchall()]
    stok_rendah = stok_perisa_low + stok_cone_low

    # Pemberitahuan Event Akan Datang (dalam 5 hari)
    today_date = datetime.now().date()
    five_days_later = today_date + timedelta(days=5)
    c.execute("""
        SELECT bil_no, nama, tel_no, tarikh, package, balance 
        FROM pesanan 
        WHERE tarikh >= ? AND tarikh <= ? 
        ORDER BY tarikh ASC
    """, (today_date.strftime('%Y-%m-%d'), five_days_later.strftime('%Y-%m-%d')))
    upcoming_events = c.fetchall()

    event_alerts = []
    for event in upcoming_events:
        event_date = datetime.strptime(event['tarikh'], '%Y-%m-%d').date()
        days_left = (event_date - today_date).days
        status = "Pending" if event['balance'] > 0 else "Done"
        event_alerts.append({
            'bil_no': event['bil_no'],
            'nama': event['nama'],
            'tarikh': event['tarikh'],
            'package': event['package'],
            'days_left': days_left,
            'status': status
        })

    conn.close()

    return render_template('home.html',
                           title="AUS Ice Cream Catering",
                           total_hasil=round(total_hasil, 2),
                           today_orders=today_orders,
                           stok_rendah=stok_rendah,
                           event_alerts=event_alerts)
						   
@app.route('/pesanan', methods=['GET', 'POST'])
def pesanan():
    conn = get_db()
    c = conn.cursor()

    if request.method == 'POST':
        nama = request.form.get('nama')
        tel_no = request.form.get('tel_no')
        tarikh = request.form.get('tarikh')
        alamat = request.form.get('alamat')
        package = request.form.get('package')
        qty = int(request.form.get('qty') or 0)
        discount = float(request.form.get('discount') or 0)
        transport = float(request.form.get('transport') or 0)
        deposit = float(request.form.get('deposit') or 0)

        harga_unit = 0.60 if package == 'MINI' else 1.00
        total_price = qty * harga_unit
        balance = total_price - discount + transport - deposit

        c.execute('''
            INSERT INTO pesanan (nama, tel_no, tarikh, alamat, package, qty, total_price, discount, transport, deposit, balance)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (nama, tel_no, tarikh, alamat, package, qty, total_price, discount, transport, deposit, balance))
        conn.commit()

        bil_no = c.lastrowid

        # Generate PDF
        pdf = FPDF(orientation='P', unit='mm', format='A4')
        pdf.add_page()

        # Header dengan logo (jika ada)
        try:
            pdf.image('static/images/auslogo.png', x=10, y=8, w=20)  # guna nama fail logo awak
        except:
            pass

        pdf.set_font("Arial", "B", 15) # tajuk utama
        pdf.cell(0, 10, txt="AUS ICE CREAM CATERING", ln=1, align="C")
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, txt="Resit Pesanan Rasmi", ln=1, align="C")
        pdf.set_font("Arial", "", 10)
        pdf.cell(0, 6, txt=f"Bil No: {bil_no} | Tarikh: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=1, align="C")
        pdf.ln(3) # kurangkan spasi

		# Garis pemisah 
        pdf.set_draw_color(255, 105, 180)
        pdf.set_line_width(0.4)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(4)

		# Maklumat Pelanggan
        pdf.set_font("Arial", "B", 10)
        pdf.cell(0, 6, txt="MAKLUMAT PELANGGAN", ln=1)
        pdf.set_font("Arial", "", 9)

        pdf.cell(40, 6, txt="Nama Pelanggan:", border=0)
        pdf.cell(150, 6, txt=nama or "-", border=0, ln=1)

        pdf.cell(40, 6, txt="No Telefon:", border=0)
        pdf.cell(150, 6, txt=tel_no or "-", border=0, ln=1)

        pdf.cell(40, 6, txt="Tarikh Event:", border=0)
        pdf.cell(150, 6, txt=tarikh or "-", border=0, ln=1)

        pdf.cell(40, 6, txt="Alamat Event:", border=0)
        pdf.multi_cell(150, 6, txt=alamat or "-", border=0)
        pdf.ln(3)

		# Butiran Pesanan
        pdf.set_font("Arial", "B", 10)
        pdf.cell(0, 6, txt="BUTIRAN PESANAN", ln=1)
        pdf.set_font("Arial", "", 9)
        pdf.set_fill_color(245, 245, 245)
        pdf.cell(55, 7, txt="Package", border=1, fill=True)
        pdf.cell(25, 7, txt="Qty", border=1, fill=True)
        pdf.cell(45, 7, txt="Harga Unit", border=1, fill=True)
        pdf.cell(45, 7, txt="Jumlah", border=1, ln=1, fill=True)

        pdf.cell(55, 7, txt=package, border=1)
        pdf.cell(25, 7, txt=str(qty), border=1, align="C")
        pdf.cell(45, 7, txt=f"RM{harga_unit:.2f}", border=1, align="R")
        pdf.cell(45, 7, txt=f"RM{total_price:.2f}", border=1, ln=1, align="R")

        pdf.ln(5)

		# Jumlah & Baki
        pdf.set_font("Arial", "B", 10)
        pdf.cell(130, 8, txt="JUMLAH BAYARAN", border=0)
        pdf.cell(60, 8, txt=f"RM{total_price:.2f}", border=0, ln=1, align="R")

        pdf.set_font("Arial", "", 9)
        pdf.cell(130, 6, txt="Diskaun", border=0)
        pdf.cell(60, 6, txt=f"- RM{discount:.2f}", border=0, ln=1, align="R")
        pdf.cell(130, 6, txt="Kos Transport", border=0)
        pdf.cell(60, 6, txt=f"+ RM{transport:.2f}", border=0, ln=1, align="R")
        pdf.cell(130, 6, txt="Deposit", border=0)
        pdf.cell(60, 6, txt=f"- RM{deposit:.2f}", border=0, ln=1, align="R")

        pdf.set_font("Arial", "B", 12)
        pdf.set_text_color(236, 64, 122)
        pdf.cell(140, 12, txt="BAKI BAYARAN", border=0)
        pdf.cell(50, 12, txt=f"RM{balance:.2f}", border=0, ln=1, align="R")

        # Teks terima kasih & hubungi kami (satu baris atas satu baris)
        pdf.ln(10)
        pdf.set_font("Arial", "I", 9)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 5, txt="Terima kasih atas tempahan anda!", ln=1, align="C")
        pdf.cell(0, 5, txt="Baki bayaran hendaklah dijelaskan 3 hari sebelum tarikh majlis.", ln=1, align="C")
        pdf.ln(3)
        pdf.cell(0, 5, txt="Hubungi kami jika ada sebarang pertanyaan:", ln=1, align="C")
        pdf.cell(0, 5, txt="011-15371071 / 014-4007237", ln=1, align="C")
        pdf.ln(3)


        # Bank Info (kecilkan & padatkan)
        pdf.set_font("Arial", "B", 9)
        pdf.set_text_color(236, 64, 122)
        pdf.cell(0, 6, txt="Maklumat Pembayaran", ln=1)
        pdf.set_font("Arial", "", 9)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 5, txt="Maybank Acc No: 151520082883", ln=1)
        pdf.cell(0, 5, txt="NORMI IDAYU BINTI YUNOS", ln=1)

        # Output PDF ke memory untuk download
        pdf_output = BytesIO()
        pdf.output(pdf_output)
        pdf_output.seek(0)

        # Simpan PDF ke folder resit (guna nama fail sahaja untuk DB)
        resit_filename = f"Resit_Bil{bil_no}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        resit_filepath = os.path.join(RESIT_PATH, resit_filename)
        with open(resit_filepath, 'wb') as f:
            f.write(pdf_output.getvalue())

        # Simpan NAMA FAIL SAHAJA ke database
        c.execute("UPDATE pesanan SET resit_path = ? WHERE bil_no = ?", (resit_filename, bil_no))
        conn.commit()

        # Return PDF untuk download
        pdf_output.seek(0)  # reset pointer supaya tak kosong
        conn.close()

        return send_file(
            pdf_output,
            as_attachment=False,
            download_name=resit_filename,
            mimetype='application/pdf'
        )

		
    # GET: senarai pesanan + status Pending/Done
    c.execute("SELECT bil_no, nama, tarikh, package, qty, total_price, balance, resit_path FROM pesanan ORDER BY bil_no DESC LIMIT 10")
    pesanan_list = c.fetchall()
    conn.close()

    return render_template('pesanan.html', pesanan_list=pesanan_list, title="Pesanan")
	
	
@app.route('/mark_done/<int:bil_no>', methods=['POST'])
def mark_done(bil_no):
    conn = get_db()
    c = conn.cursor()
    
    # Set balance = 0 untuk pesanan ini
    c.execute("UPDATE pesanan SET balance = 0 WHERE bil_no = ?", (bil_no,))
    conn.commit()
    conn.close()
    
    # Kembali ke halaman pesanan
    return redirect(url_for('pesanan'))	
	
# Route Stock
@app.route('/stock', methods=['GET', 'POST'])
def stock():
    conn = get_db()
    c = conn.cursor()

    if request.method == 'POST':
        # Update stok perisa atau cone
        item_type = request.form.get('item_type')
        item = request.form.get('item')
        in_qty = int(request.form.get('in_qty') or 0)
        out_qty = int(request.form.get('out_qty') or 0)

        table = 'stock_perisa' if item_type == 'perisa' else 'stock_cone'
        column = 'perisa' if item_type == 'perisa' else 'cone'

        c.execute(f"UPDATE {table} SET in_qty = in_qty + ?, out_qty = out_qty + ?, balance = balance + ? - ? WHERE {column} = ?", (in_qty, out_qty, in_qty, out_qty, item))
        conn.commit()

    # Papar stok
    c.execute("SELECT * FROM stock_perisa")
    perisa = c.fetchall()
    c.execute("SELECT * FROM stock_cone")
    cone = c.fetchall()
    conn.close()

    return render_template('stock.html', perisa=perisa, cone=cone, title="Stock")

# Route Summary
@app.route('/summary', methods=['GET', 'POST'])
def summary():
    conn = get_db()
    c = conn.cursor()

    tahun = request.form.get('tahun') or datetime.now().year
    tahun_list = list(range(2020, datetime.now().year + 5))  # Contoh tahun

    # Jumlah tempahan & hasil tahun pilihan
    c.execute("SELECT COUNT(*), SUM(total_price - deposit) FROM pesanan WHERE strftime('%Y', tarikh) = ?", (str(tahun),))
    result = c.fetchone()
    tahun_tempahan = result[0] or 0
    tahun_hasil = result[1] or 0.0

    # Ringkasan bulanan
    bulan_nama = ["Januari", "Februari", "Mac", "April", "Mei", "Jun", "Julai", "Ogos", "September", "Oktober", "November", "Disember"]
    bulanan_data = []
    for bulan in range(1, 13):
        c.execute("SELECT COUNT(*), SUM(qty) FILTER (WHERE package = 'MINI') as qty_mini, SUM(qty) FILTER (WHERE package = 'MEDIUM') as qty_medium, SUM(total_price - deposit) FROM pesanan WHERE strftime('%Y', tarikh) = ? AND strftime('%m', tarikh) = ?", (str(tahun), f"{bulan:02d}"))
        result = c.fetchone()
        bulanan_data.append({
            'bulan': bulan_nama[bulan-1],
            'jumlah': result[0] or 0,
            'qty_mini': result[1] or 0,
            'qty_medium': result[2] or 0,
            'hasil': result[3] or 0.0
        })

    conn.close()

    return render_template('summary.html', title="Summary", tahun=tahun, tahun_list=tahun_list, tahun_tempahan=tahun_tempahan, tahun_hasil=tahun_hasil, bulanan_data=bulanan_data)

@app.route('/resit/<filename>')
def view_resit(filename):
    return send_from_directory(RESIT_PATH, filename)	
	
@app.route('/delete_pesanan/<int:bil_no>', methods=['POST'])
def delete_pesanan(bil_no):
    conn = get_db()
    c = conn.cursor()
    
    # Padam rekod pesanan
    c.execute("DELETE FROM pesanan WHERE bil_no = ?", (bil_no,))
    conn.commit()
    conn.close()
    
    # Kembali ke halaman pesanan
    return redirect(url_for('pesanan'))

@app.route('/edit_pesanan/<int:bil_no>', methods=['GET', 'POST'])
def edit_pesanan(bil_no):
    conn = get_db()
    c = conn.cursor()

    if request.method == 'POST':
        nama = request.form.get('nama')
        tel_no = request.form.get('tel_no')
        tarikh = request.form.get('tarikh')
        alamat = request.form.get('alamat')
        package = request.form.get('package')
        qty = int(request.form.get('qty') or 0)
        discount = float(request.form.get('discount') or 0)
        transport = float(request.form.get('transport') or 0)
        deposit = float(request.form.get('deposit') or 0)

        harga_unit = 0.60 if package == 'MINI' else 1.00
        total_price = qty * harga_unit
        balance = total_price - discount + transport - deposit

        c.execute('''
            UPDATE pesanan SET
                nama = ?, tel_no = ?, tarikh = ?, alamat = ?, package = ?, qty = ?,
                total_price = ?, discount = ?, transport = ?, deposit = ?, balance = ?
            WHERE bil_no = ?
        ''', (nama, tel_no, tarikh, alamat, package, qty, total_price, discount, transport, deposit, balance, bil_no))
        
        conn.commit()
        conn.close()
        return redirect(url_for('pesanan'))

    # GET: ambil data lama
    c.execute("SELECT * FROM pesanan WHERE bil_no = ?", (bil_no,))
    pesanan = c.fetchone()
    conn.close()

    if pesanan is None:
        return "Pesanan tidak dijumpai", 404

    return render_template('edit_pesanan.html', pesanan=pesanan)
@app.route('/delete_perisa/<string:perisa>', methods=['POST'])
def delete_perisa(perisa):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM stock_perisa WHERE perisa = ?", (perisa,))
    conn.commit()
    conn.close()
    return redirect(url_for('stock'))


@app.route('/delete_cone/<string:cone>', methods=['POST'])
def delete_cone(cone):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM stock_cone WHERE cone = ?", (cone,))
    conn.commit()
    conn.close()
    return redirect(url_for('stock'))

@app.route('/regenerate_resit/<int:bil_no>', methods=['POST'])
def regenerate_resit(bil_no):
    conn = get_db()
    c = conn.cursor()

    # Ambil data terkini dari database
    c.execute("SELECT nama, tel_no, tarikh, alamat, package, qty, discount, transport, deposit, balance FROM pesanan WHERE bil_no = ?", (bil_no,))
    data = c.fetchone()

    if not data:
        conn.close()
        return "Pesanan tidak dijumpai", 404

    nama, tel_no, tarikh, alamat, package, qty, discount, transport, deposit, balance = data

    harga_unit = 0.60 if package == 'MINI' else 1.00
    total_price = qty * harga_unit

    # Generate PDF baru dengan data terkini
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()


    # Header dengan logo (jika ada)
    try:
        pdf.image('static/images/auslogo.png', x=10, y=8, w=20)  # guna nama fail logo awak
    except:
        pass

    pdf.set_font("Arial", "B", 15) # tajuk utama
    pdf.cell(0, 10, txt="AUS ICE CREAM CATERING", ln=1, align="C")
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, txt="Resit Pesanan Rasmi", ln=1, align="C")
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 6, txt=f"Bil No: {bil_no} | Tarikh: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=1, align="C")
    pdf.ln(3) # kurangkan spasi

	# Garis pemisah 
    pdf.set_draw_color(255, 105, 180)
    pdf.set_line_width(0.4)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)

	# Maklumat Pelanggan
    pdf.set_font("Arial", "B", 10)
    pdf.cell(0, 6, txt="MAKLUMAT PELANGGAN", ln=1)
    pdf.set_font("Arial", "", 9)

    pdf.cell(40, 6, txt="Nama Pelanggan:", border=0)
    pdf.cell(150, 6, txt=nama or "-", border=0, ln=1)

    pdf.cell(40, 6, txt="No Telefon:", border=0)
    pdf.cell(150, 6, txt=tel_no or "-", border=0, ln=1)

    pdf.cell(40, 6, txt="Tarikh Event:", border=0)
    pdf.cell(150, 6, txt=tarikh or "-", border=0, ln=1)

    pdf.cell(40, 6, txt="Alamat Event:", border=0)
    pdf.multi_cell(150, 6, txt=alamat or "-", border=0)
    pdf.ln(3)

	# Butiran Pesanan
    pdf.set_font("Arial", "B", 10)
    pdf.cell(0, 6, txt="BUTIRAN PESANAN", ln=1)
    pdf.set_font("Arial", "", 9)
    pdf.set_fill_color(245, 245, 245)
    pdf.cell(55, 7, txt="Package", border=1, fill=True)
    pdf.cell(25, 7, txt="Qty", border=1, fill=True)
    pdf.cell(45, 7, txt="Harga Unit", border=1, fill=True)
    pdf.cell(45, 7, txt="Jumlah", border=1, ln=1, fill=True)

    pdf.cell(55, 7, txt=package, border=1)
    pdf.cell(25, 7, txt=str(qty), border=1, align="C")
    pdf.cell(45, 7, txt=f"RM{harga_unit:.2f}", border=1, align="R")
    pdf.cell(45, 7, txt=f"RM{total_price:.2f}", border=1, ln=1, align="R")

    pdf.ln(5)

	# Jumlah & Baki
    pdf.set_font("Arial", "B", 10)
    pdf.cell(130, 8, txt="JUMLAH BAYARAN", border=0)
    pdf.cell(60, 8, txt=f"RM{total_price:.2f}", border=0, ln=1, align="R")

    pdf.set_font("Arial", "", 9)
    pdf.cell(130, 6, txt="Diskaun", border=0)
    pdf.cell(60, 6, txt=f"- RM{discount:.2f}", border=0, ln=1, align="R")
    pdf.cell(130, 6, txt="Kos Transport", border=0)
    pdf.cell(60, 6, txt=f"+ RM{transport:.2f}", border=0, ln=1, align="R")
    pdf.cell(130, 6, txt="Deposit", border=0)
    pdf.cell(60, 6, txt=f"- RM{deposit:.2f}", border=0, ln=1, align="R")

    pdf.set_font("Arial", "B", 12)
    pdf.set_text_color(236, 64, 122)
    pdf.cell(140, 12, txt="BAKI BAYARAN", border=0)
    pdf.cell(50, 12, txt=f"RM{balance:.2f}", border=0, ln=1, align="R")

    # Teks terima kasih & hubungi kami (satu baris atas satu baris)
    pdf.ln(10)
    pdf.set_font("Arial", "I", 9)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 5, txt="Terima kasih atas tempahan anda!", ln=1, align="C")
    pdf.cell(0, 5, txt="Baki bayaran hendaklah dijelaskan 3 hari sebelum tarikh majlis.", ln=1, align="C")
    pdf.ln(3)
    pdf.cell(0, 5, txt="Hubungi kami jika ada sebarang pertanyaan:", ln=1, align="C")
    pdf.cell(0, 5, txt="011-15371071 / 014-4007237", ln=1, align="C")
    pdf.ln(3)


    # Bank Info (kecilkan & padatkan)
    pdf.set_font("Arial", "B", 9)
    pdf.set_text_color(236, 64, 122)
    pdf.cell(0, 6, txt="Maklumat Pembayaran", ln=1)
    pdf.set_font("Arial", "", 9)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 5, txt="Maybank Acc No: 151520082883", ln=1)
    pdf.cell(0, 5, txt="NORMI IDAYU BINTI YUNOS", ln=1)
		
    # Output PDF ke memory
    pdf_output = BytesIO()
    pdf.output(pdf_output)
    pdf_output.seek(0)

    # Buat nama fail baru (bil sama + timestamp baru)
    resit_filename = f"Resit_Bil{bil_no}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_revised.pdf"
    resit_filepath = os.path.join(RESIT_PATH, resit_filename)

    with open(resit_filepath, 'wb') as f:
        f.write(pdf_output.getvalue())

    # Update resit_path dalam database dengan nama fail baru
    c.execute("UPDATE pesanan SET resit_path = ? WHERE bil_no = ?", (resit_filename, bil_no))
    conn.commit()
    conn.close()

    # Hantar PDF baru untuk download
    pdf_output.seek(0)
    return send_file(
        pdf_output,
        as_attachment=True,
        download_name=resit_filename,
        mimetype='application/pdf'
    )	
	
if __name__ == '__main__':
    app.run(debug=True)