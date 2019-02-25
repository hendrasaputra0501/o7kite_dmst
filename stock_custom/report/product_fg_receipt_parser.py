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
 
class product_fg_receipt_parser(report_sxw.rml_parse):
	def __init__(self, cr, uid, name, context=None):
		if context is None:
			context = {}
		super(product_fg_receipt_parser, self).__init__(cr, uid, name, context=context)
		
		self.localcontext.update({
			'time': time,
			'report_title' : 'Laporan Pemasukan Hasil Produksi'
			})

	def set_context(self, objects, data, ids, report_type=None):
		context_report_values = {}
		brw_model = 'stock.move'
		move_line_ids = self.pool.get(brw_model).search(self.cr, self.uid, [
								('date','>=',data['from_date']),
								('date','<=',data['to_date']),
								('type','=','internal'),
								('location_id.usage','=','production'),
								('location_dest_id.usage','=','internal'),
								('product_id.product_type','=','finish_good'),
								])
		objects = self.pool.get(brw_model).browse(self.cr, self.uid, move_line_ids)

		context_report_values.update({
			'start_date' : datetime.strptime(data['start_date'],'%Y-%m-%d').strftime('%d/%m/%Y'),
			'end_date' : datetime.strptime(data['end_date'],'%Y-%m-%d').strftime('%d/%m/%Y'),
			})

		self.localcontext.update(context_report_values)

		return super(product_fg_receipt_parser, self).set_context(
			objects, data, ids, report_type=report_type)

_column_sizes = [
	('seq', 4),
	('receipt_no', 12),
	('receipt_date', 12),
	('product_code', 15),
	('product_name', 30),
	('product_uom', 8),
	('product_qty', 15),
	('product_qty_sub', 15),
	('warehouse', 30),
]

class product_fg_receipt_xls(report_xls):
	column_sizes = [x[1] for x in _column_sizes]
	def generate_xls_report(self, parser, xls_style, data, objects, wb):
		ws = wb.add_sheet(parser.report_title[:31])
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

		# Title
		cell_style = xlwt.easyxf(xls_style['xls_title'])
		report_title = parser.report_title
		c_specs = [
			('report_title', 10, 0, 'text', report_title),
		]
		row_data = self.xls_row_template(c_specs, [x[0] for x in c_specs])
		row_pos = self.xls_write_row(
			ws, row_pos, row_data, row_style=cell_style)
		
		report_title2 = "%s"%parser.company.partner_id.name.upper()
		c_specs = [
			('report_title', 10, 0, 'text', report_title2),
		]
		row_data = self.xls_row_template(c_specs, [x[0] for x in c_specs])
		row_pos = self.xls_write_row(
			ws, row_pos, row_data, row_style=cell_style)
		
		report_title3 = "Periode %s s.d %s"%(parser.start_date, parser.end_date)
		c_specs = [
			('report_title', 10, 0, 'text', report_title3),
		]
		row_data = self.xls_row_template(c_specs, [x[0] for x in c_specs])
		row_pos = self.xls_write_row(
			ws, row_pos, row_data, row_style=cell_style)
 	
		# write empty row to define column sizes
		c_sizes = self.column_sizes
		c_specs = [('empty%s' % i, 1, c_sizes[i], 'text', None)
				   for i in range(0, len(c_sizes))]
		row_data = self.xls_row_template(c_specs, [x[0] for x in c_specs])
		row_pos = self.xls_write_row(
			ws, row_pos, row_data, set_column_size=True)
		
		# Header Table
		cell_format = xls_style['bold'] + xls_style['fill'] + xls_style['borders_all']
		cell_style = xlwt.easyxf(cell_format)
		cell_style_center = xlwt.easyxf(cell_format + xls_style['center'] + xls_style['top'])
		
		ws.write_merge(row_pos, row_pos+1, 0, 0, "No.", cell_style_center)
		ws.write_merge(row_pos, row_pos, 1, 2, "Bukti Pemasukan", cell_style_center)
		ws.write(row_pos+1, 1, "Nomor", cell_style_center)
		ws.write(row_pos+1, 2, "Tanggal", cell_style_center)
		ws.write_merge(row_pos, row_pos+1, 3, 3, "Kode\nBarang", cell_style_center)
		ws.write_merge(row_pos, row_pos+1, 4, 4, "Nama Barang", cell_style_center)
		ws.write_merge(row_pos, row_pos+1, 5, 5, "Satuan", cell_style_center)
		ws.write_merge(row_pos, row_pos, 6, 7, "Jumlah", cell_style_center)
		ws.write(row_pos+1, 6, "dari produksi", cell_style_center)
		ws.write(row_pos+1, 7, "dari subkontrak", cell_style_center)
		ws.write_merge(row_pos, row_pos+1, 8, 8, "Gudang", cell_style_center)
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
			
			c_specs = [
					('seq', 1, 0, 'number', cnt, None, ll_cell_style),
					('receipt_no', 1, 0, 'text', line.picking_id and line.picking_id.name or '', None, ll_cell_style),
				]
			
			try:
				c_specs += [
					('receipt_date', 1, 0, 'date', datetime.strptime(
						line.date, '%Y-%m-%d %H:%M:%S'), None,
					 ll_cell_style_date),
				]
			except:
				c_specs += [
					('receipt_date', 1, 0, 'text', None),
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
				('product_qty_sub', 1, 0, 'number', 0.0,
					None, ll_cell_style_decimal),
				('warehouse', 1, 0, 'text', '',
					None, ll_cell_style),
			]
			row_data = self.xls_row_template(
				c_specs, [x[0] for x in c_specs])
			row_pos = self.xls_write_row(
				ws, row_pos, row_data, ll_cell_style)

product_fg_receipt_xls('report.stock.fg.receipt.xls','stock.move', parser=product_fg_receipt_parser, header=False)