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
 
class product_report_parser(report_sxw.rml_parse):
	def __init__(self, cr, uid, name, context=None):
		if context is None:
			context = {}
		super(product_report_parser, self).__init__(cr, uid, name, context=context)
		
		self.localcontext.update({
			'time': time,
		})

	def _get_mutation(self, product_ids=False, context=None):
		"""
		@param product_ids: Ids of product
		@param states: List of states
		@param what: Tuple of
		@return:
		"""
		product_obj = self.pool.get('product.product')
		if context is None:
			context = {}
		context.update({
			'states': context.get('states',[]),
			'what': context.get('what',[]),
			'from_date' : context.get('from_date',False),
			'to_date' : context.get('to_date',False),
		})
		return product_obj.get_product_available(self.cr, self.uid, product_ids, context=context)

	def set_context(self, objects, data, ids, report_type=None):
		product_obj = self.pool.get('product.product')
		product_ids = product_obj.search(self.cr, self.uid, [('product_type','=',data['product_type'])])
		objects = product_obj.browse(self.cr, self.uid, product_ids)

		states = ['done']
		product_opening = self._get_mutation(product_ids, {'from_date':data['from_date'],'to_date':data['to_date'],\
								'what':['all_in', 'all_out'],'states':states})
		product_incoming = self._get_mutation(product_ids, {'from_date':data['from_date'],'to_date':data['to_date'],\
								'what':['in'],'states':states})
		product_outgoing = self._get_mutation(product_ids, {'from_date':data['from_date'],'to_date':data['to_date'],\
								'what':['out'],'states':states})
		product_adjustment = self._get_mutation(product_ids, {'from_date':data['from_date'],'to_date':data['to_date'],\
								'what':['adj_in','adj_out'],'states':states})
		product_closing = self._get_mutation(product_ids, {'from_date':data['from_date'],'to_date':data['to_date'],\
								'what':['all_in','all_out','in','out2','adj_in','adj_out'],'states':states})

		self.localcontext.update({
			'opening': product_opening,
			'incoming': product_incoming,
			'outgoing': product_outgoing,
			'adjustment': product_adjustment,
			'closing': product_closing,
		})

		return super(product_report_parser, self).set_context(
			objects, data, ids, report_type=report_type)
# report_sxw.report_sxw('report.beacukai.out.form':'beacukai.document.line':'beacukai/report/beacukai_line.mako', parser=product_report_parser, header=False)

_column_sizes = [
	('code', 8),
	('desc', 12),
	('uom', 8),
	('opening', 15),
	('incoming', 15),
	('outgoing', 15),
	('adjustment', 15),
	('closing', 15),
	('opname', 15),
	('selisih', 15),
]

class product_report_xls(report_xls):
	column_sizes = [x[1] for x in _column_sizes]
	def generate_xls_report(self, parser, xls_style, data, objects, wb):
		ws = wb.add_sheet("report")
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
		report_name = 'Laporan Pertanggungjawaban Barang'
		c_specs = [
			('report_name', 10, 0, 'text', report_name),
		]
		row_data = self.xls_row_template(c_specs, [x[0] for x in c_specs])
		row_pos = self.xls_write_row(
			ws, row_pos, row_data, row_style=cell_style)
		
		report_name2 = "KAWASAN BERIKAT %s"%parser.company.partner_id.name.upper()
		c_specs = [
			('report_name', 10, 0, 'text', report_name2),
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
		cell_style_center = xlwt.easyxf(cell_format + xls_style['center'])
		c_specs = [
			('code', 1, 0, 'text', _('Kode Barang'), None, cell_style_center),
			('desc', 1, 0, 'text', _('Deskripsi'), None, cell_style_center),
			('uom', 1, 0, 'text', _('Satuan'), None, cell_style_center),
			('opening', 1, 0, 'text', ('Saldo Awal'), None, cell_style_center),
			('incoming', 1, 0, 'text', _('Pemasukan'), None, cell_style_center),
			('outgoing', 1, 0, 'text', _('Pengeluaran'), None, cell_style_center),
			('adjustment', 1, 0, 'text', _('Penyesuaian'), None, cell_style_center),
			('closing', 1, 0, 'text', _('Saldo Buku'), None, cell_style_center),
			('opname', 1, 0, 'text', _('Stock Opname'), None, cell_style_center),
			('selisih', 1, 0, 'text', _('Selisih'), None, cell_style_center),
			]
		row_data = self.xls_row_template(c_specs, [x[0] for x in c_specs])
		row_pos = self.xls_write_row(
			ws, row_pos, row_data, row_style=cell_style_center)

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
		for product in objects:

			# TO DO : replace cumul amounts by xls formulas
			cnt += 1
			c_specs = [
					('code', 1, 0, 'text', product.code or '', None, ll_cell_style),
					('desc', 1, 0, 'text', product.name or '', None, ll_cell_style),
					('uom', 1, 0, 'text', product.uom_id and product.uom_id.name or '', None, ll_cell_style),
					('opening', 1, 0, 'number', parser['opening'].get(product.id,False) or 0.0, None, ll_cell_style_decimal),
					('incoming', 1, 0, 'number', parser['incoming'].get(product.id,False) or 0.0, None, ll_cell_style_decimal),
					('outgoing', 1, 0, 'number', parser['outgoing'].get(product.id,False) or 0.0, None, ll_cell_style_decimal),
					('adjustment', 1, 0, 'number', parser['adjustment'].get(product.id,False) or 0.0, None, ll_cell_style_decimal),
					('closing', 1, 0, 'number', parser['closing'].get(product.id,False) or 0.0, None, ll_cell_style_decimal),
					('opname', 1, 0, 'number', 0.0, None, ll_cell_style_decimal),
					('selisih', 1, 0, 'number', 0.0, None, ll_cell_style_decimal),
			]
			row_data = self.xls_row_template(
				c_specs, [x[0] for x in c_specs])
			row_pos = self.xls_write_row(
				ws, row_pos, row_data, ll_cell_style)

product_report_xls('report.product.mutation.report.xls','product.product', parser=product_report_parser, header=False)