from openerp.osv import fields,osv
import openerp.addons.decimal_precision as dp
from tools.translate import _
from lxml import etree
from openerp.osv.orm import setup_modifiers
from datetime import datetime
import time

class wizard_product_fg_receipt(osv.osv_memory):
	_name = "wizard.product.fg.receipt"
	_description = "Product Finish Good Receipt"
	_columns = {
		'from_date': fields.date('From'), 
		'to_date': fields.date('To'),
	}

	_defaults = {
		'from_date' : lambda *f : time.strftime('%Y-%m-01'),
		'to_date' : lambda *t : time.strftime('%Y-%m-%d'),
	}

	# def action_open_window(self, cr, uid, ids, context=None):
	# 	""" To open products income to given duration/period
	# 	 @param self: The object pointer.
	# 	 @param cr: A database cursor
	# 	 @param uid: ID of the user currently logged in
	# 	 @param ids: An ID or list of IDs (but only the first ID will be processed)
	# 	 @param context: A standard dictionary 
	# 	 @return: dictionary of action act_window product
	# 	"""
	# 	if context is None:
	# 		context = {}
	# 	wizard = self.read(cr, uid, ids, ['from_date', 'to_date','product_type'], context=context)
	# 	if wizard:
	# 		data_obj = self.pool.get('ir.model.data')
	# 		res_model = 'stock.move'
	# 		result = data_obj._get_id(cr, uid, 'stock', 'view_beacukai_document_line_in_tree')
	# 		domain = [('type','=','internal'),('state','=','done')]
	# 		view_id = data_obj.browse(cr, uid, result).res_id
			
	# 		from_date = wizard[0]['from_date']!=False and \
	# 			datetime.strptime(wizard[0]['from_date'],'%Y-%m-%d').strftime('%Y-%m-%d 00:00:00') or False
	# 		to_date = wizard[0]['to_date'] and \
	# 			datetime.strptime(wizard[0]['to_date'],'%Y-%m-%d').strftime('%Y-%m-%d 23:59:59') or False
			
	# 		domain.append(('date','>=', from_date))
	# 		domain.append(('date','<=', to_date))
	# 		return {
	# 			'name': _('Laporan Pemakaian Bahan Baku'),
	# 			'view_type': 'form',
	# 			'view_mode': 'tree',
	# 			'res_model': res_model,
	# 			'view_id':[view_id],
	# 			'type': 'ir.actions.act_window',
	# 			'context': {},
	# 			"domain":domain,
	# 		}

	def export_excel(self, cr, uid, ids, context=None):
		if context is None:
			context = {}
		wizard = self.browse(cr,uid,ids,context)[0]
		from_date = wizard.from_date!=False and \
				datetime.strptime(wizard.from_date,'%Y-%m-%d').strftime('%Y-%m-%d 00:00:00') or False
		to_date = wizard.to_date and \
				datetime.strptime(wizard.to_date,'%Y-%m-%d').strftime('%Y-%m-%d 23:59:59') or False
		datas = {
			'model': 'wizard.product.fg.receipt',
			'from_date' : from_date,
			'to_date' : to_date,
			'start_date':wizard.from_date,
			'end_date':wizard.to_date,
			}
		
		return {
				'type': 'ir.actions.report.xml',
				'report_name': 'stock.fg.receipt.xls',
				'report_type': 'xls',
				'datas': datas,
				}
wizard_product_fg_receipt()