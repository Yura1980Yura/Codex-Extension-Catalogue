from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app/skill-catalog/scripts'))
from connection_state import evaluate

class ConnectionStateTests(unittest.TestCase):
    def test_configuration_and_notes_are_not_connection_proof(self):
        for kind in ['mcp','plugin']:
            card={'configured':True,'enabled':True,'kind':kind,'profile':{'origin':'builtin'},'notes':'Подключено'}
            self.assertEqual(evaluate(card)['state'],'needs_check')

    def test_confirmed_apps_are_connected_and_disabled_overrides_evidence(self):
        card={'configured':True,'enabled':True,'runtime':'app_reported','callable':True}
        self.assertEqual(evaluate(card)['state'],'connected')
        self.assertEqual(evaluate({**card,'enabled':False})['state'],'disabled')
        self.assertEqual(evaluate({**card,'callable':False})['state'],'available')

    def test_documented_option_is_available_not_connected(self):
        self.assertEqual(evaluate({'configured':False,'enabled':False,'kind':'planned'})['state'],'available')

    def test_mcp_probe_and_authentication(self):
        card={'configured':True,'enabled':True,'kind':'mcp'}
        check={'status':'discovered','tool_count':3,'authentication':'unsupported','checked_at':'2026-10-27'}
        self.assertEqual(evaluate(card,check)['state'],'connected')
        self.assertEqual(evaluate(card,{**check,'authentication':'notLoggedIn'})['state'],'available')
        self.assertEqual(evaluate(card,{'status':'error'})['state'],'needs_check')
        self.assertEqual(evaluate(card,{**check,'tool_count':0})['state'],'needs_check')

    def test_meshy_requires_saved_key_and_successful_check(self):
        card={'id':'service:meshy','configured':True,'enabled':True,'credential_state':{'configured':True,'key_saved':True,'check':{'status':'verified'}}}
        self.assertEqual(evaluate(card)['state'],'connected')
        self.assertEqual(evaluate({**card,'credential_state':{'configured':True,'key_saved':False}})['state'],'available')
        self.assertEqual(evaluate(card,{'status':'error'})['state'],'needs_check')

if __name__=='__main__':unittest.main()
