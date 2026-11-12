"""Variable-length tool exchanges are indivisible context units."""
import sys
from pathlib import Path
import threading
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src/marionette'))
from context import fit_history, Preparation
from inference import API


def exchange(label):
    return [{'role':'user','content':label},
            {'role':'assistant','content':'','function_call':{'name':'example','arguments':'{}'},'extra':{'function_id':label}},
            {'role':'function','name':'example','content':'fact '+label,'extra':{'function_id':label}},
            {'role':'assistant','content':'answer '+label}]


class ExchangeHistoryTests(unittest.TestCase):
    def test_input_trimming_keeps_call_and_result_with_exchange(self):
        history=exchange('old')+exchange('newer')
        result,removed,_=fit_history(history,'current',lambda ms:len(ms)*10,80,20)
        self.assertEqual(removed,1)
        self.assertEqual(result,exchange('newer')+[{'role':'user','content':'current'}])
        self.assertEqual(len(history),8)
        with self.assertRaises(ValueError):fit_history(history,'too big',lambda _:100,80,20)
        self.assertEqual(len(history),8)

    def test_background_preparation_removes_complete_exchange(self):
        class Fake:
            closing=threading.Event()
            prepared=None
            def count(self,ms):return len(ms)*10
            def prepare(self,ms):self.prepared=ms
        api=Fake();history=exchange('old')+exchange('newer')
        with patch('diagnostics.log'):
            worker=Preparation(api,history,110,20)
            kept=worker.result()
        self.assertEqual(kept,exchange('newer'))
        self.assertEqual(api.prepared,exchange('newer'))
        self.assertEqual(len(history),8)

    def test_native_template_receives_calls_and_results_during_preparation(self):
        api=API('http://localhost');submitted=[]
        def request(path,body):
            submitted.append((path,body))
            if path=='/apply-template':
                return {'prompt':'prefix '+body['messages'][-1]['content']}
            return {'timings':{}}
        with patch.object(api,'json',side_effect=request),patch.object(api,'tokenize',return_value=[1,2,3]),patch('diagnostics.log'):
            api.prepare(exchange('saved'))
        messages=submitted[0][1]['messages']
        self.assertEqual(messages[1]['tool_calls'][0]['id'],'saved')
        self.assertEqual(messages[2],{'role':'tool','content':'fact saved','tool_call_id':'saved'})
        self.assertEqual(messages[3]['content'],'answer saved')
        self.assertEqual(submitted[-1][1]['prompt'],[1,2])
