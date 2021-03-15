# -*- coding: utf-8 -*-

import logging
import locale
from scrapy.http import FormRequest
from scrapy.exceptions import IgnoreRequest
from captchaMiddleware.solver import solveCaptcha
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

KEYWORDS = {"en": ["characters", "type"]}
RETRY_KEY = 'captcha_retries'


class CaptchaMiddleware(object):
    """Checks a page for a CAPTCHA test and, if present, submits a solution for it"""
    MAX_CAPTCHA_ATTEMPTS = 3

    def containsCaptchaKeywords(self, text):
        # Check that the form mentions something about CAPTCHA
        language, encoding = locale.getlocale(category=locale.LC_MESSAGES)
        if language is None:
            language = list(KEYWORDS.keys())[0]; # Must be American
        if language[0:2] in list(KEYWORDS.keys()):
            for keyword in list(KEYWORDS[language[0:2]]):
                if keyword in text.lower():
                    return True
            return False
        else:
            logger.warning("CAPTCHA keywords have not been set for this locale.")
            return None

    def findCaptchaImageUrl(self, response):
        captcha_form = response.xpath("//form[@action='/errors/validateCaptcha']")
        if not captcha_form:
            logger.debug(f'No captcha found on {response.url}')
            return None
        logger.info(f'Captcha found on {response.url}')
        image_url = captcha_form.xpath("//div[@class='a-row a-text-center']/img/@src").get()
        logger.debug(f"Captcha image URL: {image_url}")
        return image_url

    def findCaptchaField(self, page):
        soup = BeautifulSoup(page, 'lxml')
        forms = soup.find_all("form")

        if len(forms) != 1:
            logger.debug("Unable to find a form on this page.")
            return None
    
        formFields = forms[0].find_all("input")
        possibleFields = list(filter(lambda field: field["type"] != "hidden", formFields))
        if len(possibleFields) > 1:
            logger.error("Ambiguity when finding form field for CAPTCHA.")
            # Maybe we could use NLP to decide
            return None
        elif len(possibleFields) == 0:
            logger.error("Unable to find CAPTCHA form field.")
            return None
        else:
            return possibleFields[0]["name"]

    def process_response(self, request, response, spider):
        captchaUrl = self.findCaptchaImageUrl(response)
        if captchaUrl is None:
            return response; # No CAPTCHA is present
        # elif request.meta.get(RETRY_KEY, self.MAX_CAPTCHA_ATTEMPTS) == self.MAX_CAPTCHA_ATTEMPTS:
        #     logger.warning("Too many CAPTCHA attempts; surrendering.")
        #     raise IgnoreRequest
        captchaSolution = solveCaptcha(imgUrl=captchaUrl, brazen=True)
        if captchaSolution is None:
            logger.error("CAPTCHA page detected, but no solution was proposed.")
            raise IgnoreRequest
        # Return a request to submit the captcha
        logger.info("Submitting solution %s for CAPTCHA at %s", captchaSolution, captchaUrl)
        formRequest = FormRequest.from_response(
            response, formnumber=0, formdata={self.findCaptchaField(response.text):captchaSolution})
        formRequest.meta[RETRY_KEY] = request.meta.get('captcha_retries', 0) + 1
        return formRequest
