import re
import time
import xlwt
from report import report_sxw
from report_xls.report_xls import report_xls
import cStringIO
from xlwt import Workbook, Formula
from tools.translate import _
from datetime import datetime
import netsvc
 
_product_type = {
	'finish_good':'Hasil Produksi',
	'raw_material':'Bahan Baku',
	'auxiliary_material':'Bahan Penolong',
	'tools':'Alat-alat',
	'waste':'Waste/Scrap',
	'asset':'Aset',
	'others':'Barang Lainnya',
}

class beacukai_doc_report_parser(report_sxw.rml_parse):
	def __init__(self, cr, uid, name, context=None):
		if context is None:
			context = {}
		super(beacukai_doc_report_parser, self).__init__(cr, uid, name, context=context)
		report_title, shipment_type = "", ""
		if context.get('active_model',False) == 'beacukai.document.line.in':
			report_title = 'Laporan Penerimaan Barang PER DOKUMEN PABEAN'
			shipment_type = 'in'
		elif context.get('active_model',False) == 'beacukai.document.line.out':
			report_title = 'Laporan Pengeluaran Barang PER DOKUMEN PABEAN'
			shipment_type = 'out'

		self.localcontext.update({
			'time': time,
			'period_avail' : False,
			'report_title' : report_title,
			'shipment_type' : shipment_type,
			'product_type' : False,
			})
		
	def set_context(self, objects, data, ids, report_type=None):
		context_report_values = {}
		if data.get('model',False) in ('wizard.product.income','wizard.product.outgoing'):
			shipment_type = data['shipment_type']
			brw_model = 'beacukai.document.line'
			if shipment_type=='in':
				report_title = "Laporan Penerimaan"
			else:
				if data['product_type'] == 'waste':
					report_title = "Laporan Penyelesaian"
				else:
					report_title = "Laporan Pengeluaran"
		
			bcline_ids = self.pool.get(brw_model).search(self.cr, self.uid, [
									('registration_date','>=',data['from_date']),
									('registration_date','<=',data['to_date']),
									('shipment_type','=',data['shipment_type']),
									('product_id.product_type','=',data['product_type']),
									])
			if data.get('product_type',False):
				report_title = "%s %s"%(report_title,_product_type.get(data['product_type']))
			objects = self.pool.get(brw_model).browse(self.cr, self.uid, bcline_ids)

			context_report_values.update({
				'report_title': report_title,
				'period_avail' : True,
				'shipment_type': shipment_type,
				'product_type' : data['product_type'],
				'start_date' : datetime.strptime(data['from_date'],'%Y-%m-%d').strftime('%d/%m/%Y'),
				'end_date' : datetime.strptime(data['to_date'],'%Y-%m-%d').strftime('%d/%m/%Y'),
				})

		self.localcontext.update(context_report_values)

		return super(beacukai_doc_report_parser, self).set_context(
			objects, data, ids, report_type=report_type)
# report_sxw.report_sxw('report.beacukai.out.form':'beacukai.document.line':'beacukai/report/beacukai_line.mako', parser=beacukai_doc_report_parser, header=False)

_column_sizes_in = [
	('seq', 4),
	('document_type', 10),
	('registration_no', 12),
	('registration_date', 12),
	('bc_seq', 10),
	('picking_no', 12),
	('picking_date', 12),
	('product_code', 15),
	('product_name', 30),
	('product_uom', 8),
	('product_qty', 15),
	('currency_id', 7),
	('price_unit', 15),
	('subcont', 12),
	('warehouse', 12),
	('source_country', 12),
]
_column_sizes_out = [
	('seq', 4),
	('peb_number', 12),
	('peb_date', 12),
	('registration_no', 12),
	('registration_date', 12),
	('picking_no', 12),
	('picking_date', 12),
	('partner', 30),
	('product_code', 15),
	('product_name', 30),
	('product_uom', 8),
	('product_qty', 15),
	('currency_id', 7),
	('price_unit', 15),
]

_document_type = {
	'23':'BC 2.3',
	'25':'BC 2.5',
	'261':'BC 2.61',
	'262':'BC 2.62',
	'27in':'BC 2.7 Masukan',
	'27out':'BC 2.7 Keluaran',
	'30':'BC 3.0',
	'40':'BC 4.0',
	'41':'BC 4.1',
}

class beacukai_doc_report_xls(report_xls):
	column_sizes_in = [x[1] for x in _column_sizes_in]
	column_sizes_out = [x[1] for x in _column_sizes_out]
	# document_type = _document_type.copy()
	def generate_xls_report(self, parser, xls_style, data, objects, wb):
		ws = wb.add_sheet("Template")
		ws.panes_frozen = True
		ws.remove_splits = True
		ws.portrait = 0  # Landscape
		ws.fit_width_to_pages = 1
		ws.preview_magn = 90
		ws.normal_magn = 90
		ws.print_scaling = 100
		ws.page_preview = True
		# ws.set_fit_width_to_pages(1)
		row_pos = 0

		# set print header/footer
		ws.header_str = self.xls_headers['standard']
		ws.footer_str = self.xls_footers['standard']

		# cf. account_report_general_ledger.mako
		
		# initial_balance_text = {'initial_balance': _('Computed'),
		# 						'opening_balance': _('Opening Entries'),
		# 						False: _('No')}

		# Title
		cell_style = xlwt.easyxf(xls_style['xls_title'])
		report_title = parser.report_title
		c_specs = [
			('report_title', 1, 0, 'text', report_title),
		]
		row_data = self.xls_row_template(c_specs, [x[0] for x in c_specs])
		row_pos = self.xls_write_row(
			ws, row_pos, row_data, row_style=cell_style)
		
		report_title2 = "%s"%parser.company.partner_id.name.upper()
		c_specs = [
			('report_title', 1, 0, 'text', report_title2),
		]
		row_data = self.xls_row_template(c_specs, [x[0] for x in c_specs])
		row_pos = self.xls_write_row(
			ws, row_pos, row_data, row_style=cell_style)
		
		if parser.period_avail:
			report_title3 = "Periode %s s.d %s"%(parser.start_date, parser.end_date)
			c_specs = [
				('report_title', 1, 0, 'text', report_title3),
			]
			row_data = self.xls_row_template(c_specs, [x[0] for x in c_specs])
			row_pos = self.xls_write_row(
				ws, row_pos, row_data, row_style=cell_style)
 	
		# write empty row to define column sizes
		if parser.shipment_type=='in':
			c_sizes = self.column_sizes_in
		else:
			c_sizes = self.column_sizes_out
		c_specs = [('empty%s' % i, 1, c_sizes[i], 'text', None)
				   for i in range(0, len(c_sizes))]
		row_data = self.xls_row_template(c_specs, [x[0] for x in c_specs])
		row_pos = self.xls_write_row(
			ws, row_pos, row_data, set_column_size=True)
		
		# Header Table
		cell_format = xls_style['bold'] + xls_style['fill'] + xls_style['borders_all']
		cell_style = xlwt.easyxf(cell_format)
		cell_style_center = xlwt.easyxf(cell_format + xls_style['center'] + xls_style['top'])
		
		if parser.shipment_type=='in':
			ws.write_merge(row_pos, row_pos+1, 0, 0, "No.", cell_style_center)
			ws.write_merge(row_pos, row_pos+1, 1, 1, "Jenis\nDokumen", cell_style_center)
			ws.write_merge(row_pos, row_pos, 2, 4, "Dokumen Pabean", cell_style_center)
			ws.write(row_pos+1, 2, "Nomor", cell_style_center)
			ws.write(row_pos+1, 3, "Tanggal", cell_style_center)
			ws.write(row_pos+1, 4, "Nomor\nseri\nbarang", cell_style_center)
			ws.write_merge(row_pos, row_pos, 5, 6, parser.shipment_type=='in' and "Bukti Penerimaan Barang" or "Bukti Pengeluaran", cell_style_center)
			ws.write(row_pos+1, 5, "Nomor", cell_style_center)
			ws.write(row_pos+1, 6, "Tanggal", cell_style_center)
			# ws.write_merge(row_pos, row_pos+1, 7, 7, (parser.shipment_type=='in' and 'Supplier' or (shipment_type=='out' and 'Customer' or 'Invalid Partner')), cell_style_center)
			ws.write_merge(row_pos, row_pos+1, 7, 7, "Kode\nBarang", cell_style_center)
			ws.write_merge(row_pos, row_pos+1, 8, 8, "Nama Barang", cell_style_center)
			ws.write_merge(row_pos, row_pos+1, 9, 9, "Satuan", cell_style_center)
			ws.write_merge(row_pos, row_pos+1, 10, 10, "Jumlah", cell_style_center)
			ws.write_merge(row_pos, row_pos+1, 11, 11, "Mata\nUang", cell_style_center)
			ws.write_merge(row_pos, row_pos+1, 12, 12, "Nilai\nBarang", cell_style_center)
			ws.write_merge(row_pos, row_pos+1, 13, 13, "Gudang", cell_style_center)
			ws.write_merge(row_pos, row_pos+1, 14, 14, "Penerima\nSubkontrak", cell_style_center)
			ws.write_merge(row_pos, row_pos+1, 15, 15, "Negara\nasal\nbarang", cell_style_center)
		elif parser.shipment_type=='out':
			if parser.product_type and parser.product_type == 'finish_good':
				ws.write_merge(row_pos, row_pos+1, 0, 0, "No.", cell_style_center)
				ws.write_merge(row_pos, row_pos, 1, 2, "PEB", cell_style_center)
				ws.write(row_pos+1, 1, "Nomor", cell_style_center)
				ws.write(row_pos+1, 2, "Tanggal", cell_style_center)
				ws.write_merge(row_pos, row_pos, 3, 4, parser.shipment_type=='in' and "Bukti Penerimaan Barang" or "Bukti Pengeluaran", cell_style_center)
				ws.write(row_pos+1, 3, "Nomor", cell_style_center)
				ws.write(row_pos+1, 4, "Tanggal", cell_style_center)
				ws.write_merge(row_pos, row_pos+1, 5, 5, (parser.shipment_type=='in' and 'Supplier' or (parser.shipment_type=='out' and 'Customer' or 'Invalid Partner')), cell_style_center)
				ws.write_merge(row_pos, row_pos+1, 6, 6, "Kode\nBarang", cell_style_center)
				ws.write_merge(row_pos, row_pos+1, 7, 7, "Nama Barang", cell_style_center)
				ws.write_merge(row_pos, row_pos+1, 8, 8, "Satuan", cell_style_center)
				ws.write_merge(row_pos, row_pos+1, 9, 9, "Jumlah", cell_style_center)
				ws.write_merge(row_pos, row_pos+1, 10, 10, "Mata\nUang", cell_style_center)
				ws.write_merge(row_pos, row_pos+1, 11, 11, "Nilai\nBarang", cell_style_center)
			elif parser.product_type and parser.product_type == 'waste':
				ws.write_merge(row_pos, row_pos+1, 0, 0, "No.", cell_style_center)
				ws.write_merge(row_pos, row_pos, 1, 2, "BC 2.4", cell_style_center)
				ws.write(row_pos+1, 1, "Nomor", cell_style_center)
				ws.write(row_pos+1, 2, "Tanggal", cell_style_center)
				ws.write_merge(row_pos, row_pos, 3, 4, parser.shipment_type=='in' and "Bukti Penerimaan Barang" or "Bukti Pengeluaran", cell_style_center)
				ws.write(row_pos+1, 3, "Nomor", cell_style_center)
				ws.write(row_pos+1, 4, "Tanggal", cell_style_center)
				ws.write_merge(row_pos, row_pos+1, 5, 5, "Kode\nBarang", cell_style_center)
				ws.write_merge(row_pos, row_pos+1, 6, 6, "Nama Barang", cell_style_center)
				ws.write_merge(row_pos, row_pos+1, 7, 7, "Satuan", cell_style_center)
				ws.write_merge(row_pos, row_pos+1, 8, 8, "Jumlah", cell_style_center)
				ws.write_merge(row_pos, row_pos+1, 9, 9, "Mata\nUang", cell_style_center)
				ws.write_merge(row_pos, row_pos+1, 10, 10, "Nilai\nBarang", cell_style_center)
		row_pos+=2
		
		ws.set_horz_split_pos(row_pos)

		# cell styles for ledger lines
		ll_cell_format = xls_style['borders_all'] + xls_style['wrap'] + xls_style['top']
		ll_cell_style = xlwt.easyxf(ll_cell_format)
		ll_cell_style_center = xlwt.easyxf(ll_cell_format + xls_style['center'])
		ll_cell_style_date = xlwt.easyxf(
			ll_cell_format + xls_style['left'],
			num_format_str=report_xls.date_format)
		ll_cell_style_decimal = xlwt.easyxf(
			ll_cell_format + xls_style['right'],
			num_format_str=report_xls.decimal_format)

		cnt = 0
		for line in objects:
			# TO DO : replace cumul amounts by xls formulas
			cnt += 1
			cumul_debit = 0.0
			if parser.shipment_type=='in':
				c_specs = [
						('seq', 1, 0, 'number', cnt, None, ll_cell_style),
						('document_type', 1, 0, 'text', _document_type.get(line.document_type,False) and _document_type[line.document_type] or '', None, ll_cell_style),
						('registration_no', 1, 0, 'text', line.registration_no, None, ll_cell_style),
					]
				
				try:
					c_specs += [
						('registration_date', 1, 0, 'date', datetime.strptime(
							line.registration_date, '%Y-%m-%d'), None,
						 ll_cell_style_date),
					]
				except:
					c_specs += [
						('registration_date', 1, 0, 'text', None),
					]

				c_specs += [
					('seq_no', 1, 0, 'text', '', None, ll_cell_style),
					('picking_no', 1, 0, 'text', line.picking_no or ''),
					]

				try:
					c_specs += [
						('picking_date', 1, 0, 'date', datetime.strptime(
							line.picking_date, '%Y-%m-%d'), None,
						 ll_cell_style_date),
					]
				except:
					c_specs += [
						('picking_date', 1, 0, 'text', None),
					]

				c_specs+=[
					# ('partner', 1, 0, 'text', (line.shipment_type=='in' and (line.source_partner_id and line.source_partner_id.name or '') or (line.dest_partner_id and line.dest_partner_id.name or '')) or '',
						# None, ll_cell_style),
					('product_code', 1, 0, 'text', line.product_id and line.product_id.default_code or '',
						None, ll_cell_style),
					('product_name', 1, 0, 'text', line.product_id and line.product_id.name or '',
						None, ll_cell_style),
					('product_uom', 1, 0, 'text', line.product_uom and line.product_uom.name or '',
						None, ll_cell_style),
					('product_qty', 1, 0, 'number', line.product_qty or 0.0,
						None, ll_cell_style_decimal),
					('currency_id', 1, 0, 'text', line.currency_id and line.currency_id.name or '',
						None, ll_cell_style),
					('price_unit', 1, 0, 'number', line.price_subtotal or 0.0,
						None, ll_cell_style_decimal),
					('warehouse', 1, 0, 'text', '',
						None, ll_cell_style),
					('subcont', 1, 0, 'text', '',
						None, ll_cell_style),
					('source_country', 1, 0, 'text', '',
						None, ll_cell_style),
				]
			elif parser.shipment_type=='out':
				if parser.product_type and parser.product_type=='finish_good':
					c_specs = [
							('seq', 1, 0, 'number', cnt, None, ll_cell_style),
							('peb_number', 1, 0, 'text', line.peb_number, None, ll_cell_style),
						]
					
					try:
						c_specs += [
							('peb_date', 1, 0, 'date', datetime.strptime(
								line.peb_date, '%Y-%m-%d'), None,
							 ll_cell_style_date),
						]
					except:
						c_specs += [
							('peb_date', 1, 0, 'text', None),
						]

					c_specs += [
						('picking_no', 1, 0, 'text', line.picking_no or ''),
						]

					try:
						c_specs += [
							('picking_date', 1, 0, 'date', datetime.strptime(
								line.picking_date, '%Y-%m-%d'), None,
							 ll_cell_style_date),
						]
					except:
						c_specs += [
							('picking_date', 1, 0, 'text', None),
						]

					c_specs+=[
						('partner', 1, 0, 'text', (parser.shipment_type=='in' and (line.source_partner_id and line.source_partner_id.name or '') or (line.dest_partner_id and line.dest_partner_id.name or '')) or '',
							None, ll_cell_style),
						('product_code', 1, 0, 'text', line.product_id and line.product_id.default_code or '',
							None, ll_cell_style),
						('product_name', 1, 0, 'text', line.product_id and line.product_id.name or '',
							None, ll_cell_style),
						('product_uom', 1, 0, 'text', line.product_uom and line.product_uom.name or '',
							None, ll_cell_style),
						('product_qty', 1, 0, 'number', line.product_qty or 0.0,
							None, ll_cell_style_decimal),
						('currency_id', 1, 0, 'text', line.currency_id and line.currency_id.name or '',
							None, ll_cell_style),
						('price_unit', 1, 0, 'number', line.price_subtotal or 0.0,
							None, ll_cell_style_decimal),
					]
				elif parser.product_type and parser.product_type=='waste':
					c_specs = [
							('seq', 1, 0, 'number', cnt, None, ll_cell_style),
							('bc_number', 1, 0, 'text', line.registration_no, None, ll_cell_style),
						]
					
					try:
						c_specs += [
							('bc_date', 1, 0, 'date', datetime.strptime(
								line.registration_date, '%Y-%m-%d'), None,
							 ll_cell_style_date),
						]
					except:
						c_specs += [
							('bc_date', 1, 0, 'text', None),
						]

					c_specs += [
						('picking_no', 1, 0, 'text', line.picking_no or ''),
						]

					try:
						c_specs += [
							('picking_date', 1, 0, 'date', datetime.strptime(
								line.picking_date, '%Y-%m-%d'), None,
							 ll_cell_style_date),
						]
					except:
						c_specs += [
							('picking_date', 1, 0, 'text', None),
						]

					c_specs+=[
						('product_code', 1, 0, 'text', line.product_id and line.product_id.default_code or '',
							None, ll_cell_style),
						('product_name', 1, 0, 'text', line.product_id and line.product_id.name or '',
							None, ll_cell_style),
						('product_uom', 1, 0, 'text', line.product_uom and line.product_uom.name or '',
							None, ll_cell_style),
						('product_qty', 1, 0, 'number', line.product_qty or 0.0,
							None, ll_cell_style_decimal),
						('currency_id', 1, 0, 'text', line.currency_id and line.currency_id.name or '',
							None, ll_cell_style),
						('price_unit', 1, 0, 'number', line.price_subtotal or 0.0,
							None, ll_cell_style_decimal),
					]
			row_data = self.xls_row_template(
				c_specs, [x[0] for x in c_specs])
			row_pos = self.xls_write_row(
				ws, row_pos, row_data, ll_cell_style)

beacukai_doc_report_xls('report.beacukai.in.form.xls','beacukai.document.line', parser=beacukai_doc_report_parser, header=False)
beacukai_doc_report_xls('report.beacukai.out.form.xls','beacukai.document.line', parser=beacukai_doc_report_parser, header=False)
