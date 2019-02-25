from openerp.osv import fields,osv
import openerp.addons.decimal_precision as dp
from tools.translate import _
from lxml import etree
from openerp.osv.orm import setup_modifiers
from datetime import datetime
import time

class wizard_product_work_in_process(osv.osv_memory):
	_inherit = "wizard.product.work.in.process"
	_columns = {
		# 'product_type' : fields.selection([
		# 	('finish_good','Finish Goods'),
		# 	('raw_material','Raw Materials'),
		# 	], 'Product Type',required=True),
	}

	_defaults = {
		# 'product_type' : lambda *p : 'finish_good',
	}

	def action_open_window(self, cr, uid, ids, context=None):
		""" To open products mutation to given duration/period
		 @param self: The object pointer.
		 @param cr: A database cursor
		 @param uid: ID of the user currently logged in
		 @param ids: An ID or list of IDs (but only the first ID will be processed)
		 @param context: A standard dictionary 
		 @return: dictionary of action act_window product
		"""
		if context is None:
			context = {}
		wizard = self.read(cr, uid, ids, ['from_date', 'to_date','product_type'], context=context)
		if wizard:
			data_obj = self.pool.get('ir.model.data')
			domain = []
			# if wizard[0]['product_type']=='finish_good':
			# 	res_model = 'product.blend'
			# 	result = data_obj._get_id(cr, uid, 'stock_custom', 'view_product_wip_blend_tree2_mutation')
			# elif wizard[0]['product_type']=='raw_material':
			res_model = 'product.rm.category'
			result = data_obj._get_id(cr, uid, 'stock_custom', 'view_product_wip_rm_category_tree2_mutation')
			# else:
			# 	res_model = 'product.product'
			# 	result = data_obj._get_id(cr, uid, 'master_data_custom', 'view_product_tree2_mutation')
			# 	domain = [('product_type','=',wizard[0]['product_type']),('type','<>','service')]
			view_id = data_obj.browse(cr, uid, result).res_id
			
			from_date = wizard[0]['from_date']!=False and \
				datetime.strptime(wizard[0]['from_date'],'%Y-%m-%d').strftime('%Y-%m-%d 00:00:00') or False
			to_date = wizard[0]['to_date'] and \
				datetime.strptime(wizard[0]['to_date'],'%Y-%m-%d').strftime('%Y-%m-%d 23:59:59') or False
			
			return {
				'name': _('Laporan Barang Work-in-Process'),
				'view_type': 'form',
				'view_mode': 'tree',
				'res_model': res_model,
				'view_id':[view_id],
				'type': 'ir.actions.act_window',
				'context': {'from_date': from_date or False,
							'to_date': to_date or False,},
				"domain":domain,
			}

	def export_excel(self, cr, uid, ids, context=None):
		if context is None:
			context = {}
		wizard = self.browse(cr,uid,ids,context)[0]
		datas = {
			'model': 'wizard.product.work.in.process',
			'from_date' : wizard.from_date,
			'to_date' : wizard.to_date,
			'product_type':wizard.product_type,
			}
		if wizard.product_type=='finish_good':
			report_name = 'blend.wip.report.xls'
		else:
			report_name = 'rm.categ.wip.report.xls'

		return {
				'type': 'ir.actions.report.xml',
				'report_name': report_name,
				'report_type': 'xls',
				'datas': datas,
				}

wizard_product_work_in_process()