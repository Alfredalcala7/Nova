"""Tests for Nova 2.0: file reading, AI quizzes, saved chats, and the local web server's safety rules."""
import base64
import io
import json
import sys
import unittest
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services import ai_service, chat_service, file_service  # noqa: E402
from tests.test_services import DatabaseTestCase  # noqa: E402


def make_zip(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, text in files.items():
            archive.writestr(name, text)
    return buffer.getvalue()


class FileServiceTests(unittest.TestCase):
    def test_docx_text_is_extracted(self):
        data = make_zip({"word/document.xml": "<w:document><w:p><w:r><w:t>Hello &amp; welcome</w:t></w:r></w:p><w:p><w:r><w:t>Second</w:t></w:r></w:p></w:document>"})
        item = file_service.read_material("notes.docx", data)
        self.assertEqual(item["kind"], "text")
        self.assertEqual(item["text"], "Hello & welcome\nSecond")

    def test_pptx_slides_are_numbered_in_order(self):
        data = make_zip({"ppt/slides/slide2.xml": "<a:p><a:r><a:t>Two</a:t></a:r></a:p>", "ppt/slides/slide10.xml": "<a:p><a:r><a:t>Ten</a:t></a:r></a:p>", "ppt/slides/slide1.xml": "<a:p><a:r><a:t>One</a:t></a:r></a:p>"})
        text = file_service.read_material("deck.pptx", data)["text"]
        self.assertLess(text.index("One"), text.index("Two"))
        self.assertLess(text.index("Two"), text.index("Ten"))

    def test_images_and_pdfs_pass_through(self):
        self.assertEqual(file_service.read_material("a.PNG", b"\x89PNGdata")["mime"], "image/png")
        self.assertEqual(file_service.read_material("a.pdf", b"%PDF-1.4 x")["kind"], "pdf")

    def test_bad_files_are_refused_with_friendly_messages(self):
        for name, data in [("a.pdf", b"not a pdf"), ("a.exe", b"MZ"), ("a.doc", b"x"), ("a.txt", b""), ("a.docx", b"junk")]:
            with self.assertRaises(file_service.FileError, msg=name):
                file_service.read_material(name, data)

    def test_size_and_count_limits(self):
        with self.assertRaises(file_service.FileError):
            file_service.read_material("big.txt", b"x" * (file_service.MAX_FILE_BYTES + 1))
        many = [{"name": f"{i}.txt", "data": base64.b64encode(b"hi").decode()} for i in range(file_service.MAX_FILES + 1)]
        with self.assertRaises(file_service.FileError):
            file_service.read_many(many)


class QuizGenerationTests(unittest.TestCase):
    GOOD = {"question": "What is 2+2?", "choices": ["3", "4", "5", "6"], "correct": 2, "explanation": "Basic sums."}

    def test_clean_questions_keeps_the_right_answer_after_shuffling(self):
        for _ in range(20):
            (item,) = ai_service.clean_questions([self.GOOD])
            self.assertEqual(item["choices"][item["correct"] - 1], "4")

    def test_malformed_questions_are_dropped(self):
        bad = [{"question": "x", "choices": ["a", "b", "c"], "correct": 1}, {"question": "x", "choices": ["a", "a", "b", "c"], "correct": 1},
               {"question": "x", "choices": ["a", "b", "c", "d"], "correct": 9}, {"choices": ["a", "b", "c", "d"], "correct": 1}, "nonsense"]
        self.assertEqual(ai_service.clean_questions(bad), [])

    def test_json_is_found_inside_fences_and_wrappers(self):
        wrapped = "Sure!\n```json\n" + json.dumps({"questions": [self.GOOD]}) + "\n```"
        self.assertEqual(len(ai_service._parse_json_list(wrapped)), 1)
        with self.assertRaises(ValueError):
            ai_service._parse_json_list("no json here")

    def test_generate_quiz_end_to_end_with_fake_provider(self):
        import os
        os.environ["ANTHROPIC_API_KEY"] = "x" * 30
        os.environ.pop("GEMINI_API_KEY", None)
        ai_service._requests_made = 0
        seen = {}

        class Reply:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return json.dumps({"content": [{"type": "text", "text": json.dumps([TestData.GOOD] * 3)}]}).encode()

        def opener(request, timeout=0):
            seen["body"] = json.loads(request.data)
            return Reply()

        TestData.GOOD = self.GOOD
        pdf = {"kind": "pdf", "mime": "application/pdf", "data": "AAAA", "text": None, "name": "x.pdf"}
        questions = ai_service.generate_quiz({"text": "", "attachments": [pdf]}, 3, "easy", opener)
        self.assertEqual(len(questions), 3)
        block = seen["body"]["messages"][0]["content"][0]
        self.assertEqual(block["type"], "document")  # the PDF itself was sent to the model
        self.assertIn("JSON array", seen["body"]["system"])
        os.environ.pop("ANTHROPIC_API_KEY")


class TestData:
    GOOD = None


class ChatStorageTests(DatabaseTestCase):
    def test_threads_and_messages_round_trip(self):
        thread = chat_service.create_thread("Biology help")
        chat_service.add_message(thread, "user", "hi", [{"name": "a.txt", "kind": "text", "text": "body"}])
        chat_service.add_message(thread, "assistant", "hello")
        messages = chat_service.get_messages(thread)
        self.assertEqual([m["role"] for m in messages], ["user", "assistant"])
        self.assertEqual(messages[0]["files"][0]["text"], "body")
        chat_service.delete_thread(thread)
        self.assertEqual(chat_service.get_messages(thread), [])

    def test_generated_quiz_is_saved_with_explanations(self):
        import api
        result = api.save_generated_quiz(None, "AI quizzes", "From my file", [QuizGenerationTests.GOOD])
        self.assertEqual(result["saved"], 1)
        (question,) = api.questions(result["subject_id"])
        self.assertEqual(question["explanation"], "Basic sums.")


class ServerSafetyTests(DatabaseTestCase):
    def test_requests_without_the_token_are_refused(self):
        import server
        httpd = server.make_server()
        server.start(httpd)
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        try:
            request = urllib.request.Request(base + "/api/call", data=b'{"fn":"list_subjects","args":[]}', method="POST", headers={"Content-Type": "application/json"})
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(request)
            self.assertEqual(caught.exception.code, 403)
            request = urllib.request.Request(base + "/api/call", data=b'{"fn":"list_subjects","args":[]}', method="POST", headers={"X-Nova-Token": server.TOKEN})
            self.assertTrue(json.load(urllib.request.urlopen(request))["ok"])
            with self.assertRaises(urllib.error.HTTPError):
                urllib.request.urlopen(base + "/../api.py")  # the server only serves the web folder
        finally:
            httpd.shutdown()
            httpd.server_close()


if __name__ == "__main__":
    unittest.main()
