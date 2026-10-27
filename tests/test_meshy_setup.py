import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import urllib.error

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app/skill-catalog/scripts'))
import meshy_setup as m
from storage import atomic_json

class MeshyTests(unittest.TestCase):
    key='msy_'+'testOnlyNotARealKey'*3

    def test_only_free_endpoint_and_no_redirects(self):
        opener=Mock()
        opener.open.return_value=io.BytesIO(b'{"balance":125}')
        result=m.balance(self.key,opener)
        request=opener.open.call_args.args[0]
        self.assertEqual(request.full_url,m.BALANCE_URL)
        self.assertEqual(request.method,'GET')
        self.assertEqual(result['cost_credits'],0)
        self.assertNotIn(self.key,json.dumps(result))
        with self.assertRaises(urllib.error.HTTPError):
            m.NoRedirect().redirect_request(request,None,302,'',{},'https://elsewhere.invalid')

    def test_errors_never_echo_key(self):
        for error in [RuntimeError(self.key),urllib.error.HTTPError(m.BALANCE_URL,401,self.key,{},None)]:
            opener=Mock();opener.open.side_effect=error
            with self.assertRaises(ValueError) as caught:m.balance(self.key,opener)
            self.assertNotIn(self.key,str(caught.exception))
        for value in [None,{},'bad-secret-value']:
            with self.assertRaises(ValueError):m.validate_key(value)

    def test_rejected_key_and_stale_form_never_replace_credential(self):
        state={'credential_input_available':True,'revision':'rev'}
        check=Mock(side_effect=ValueError('rejected'));write=Mock()
        with patch.object(m,'status',return_value=state):
            with self.assertRaises(ValueError):m.save_key('.',None,self.key,'rev',check,write)
            with self.assertRaises(ValueError):m.save_key('.',None,self.key,'old',check,write)
        write.assert_not_called();self.assertEqual(check.call_count,1)

    def test_verified_key_not_written_to_catalogue_or_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp);data=home/'data';data.mkdir()
            state={'credential_input_available':True,'revision':'rev'}
            verified={'status':'verified','checked_at':'2026-10-27','balance':125,'cost_credits':0}
            write=Mock()
            with patch.object(m,'status',return_value=state):
                result=m.save_key(data,home,self.key,'rev',lambda k:verified,write)
            write.assert_called_once_with(self.key)
            self.assertTrue(result['saved'])
            for path in home.rglob('*'):
                if path.is_file():self.assertNotIn(self.key,path.read_text('utf-8'))

    def test_status_hides_raw_config_and_credential(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp);base=m.root(home)
            atomic_json(base/'connection.json',{'server_name':'meshy-mcp-server','version':'0.6.6','tool_names':['generate'],'paid_tool_names':['generate']})
            launcher=str(home/'Applications/Naviki/manager/meshy_launcher.py')
            (home/'.codex/config.toml').write_text('[mcp_servers.meshy-mcp-server]\nargs='+json.dumps([launcher])+'\nenabled_tools=["generate"]\ndefault_tools_approval_mode="prompt"\n[mcp_servers.meshy-mcp-server.env]\nMESHY_API_KEY="'+self.key+'"','utf-8')
            with patch.object(m.vault,'read',return_value=True):state=m.status(home)
            self.assertTrue(state['configured']);self.assertTrue(state['paid_tools_enabled'])
            self.assertEqual(state['approval_mode'],'prompt');self.assertNotIn(self.key,json.dumps(state))

if __name__=='__main__':unittest.main()
