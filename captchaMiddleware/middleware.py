# -*- coding: utf-8 -*-

import logging
import locale
from scrapy.http import FormRequest
from scrapy.exceptions import IgnoreRequest
from captchaMiddleware.solver import solveCaptcha


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


    def findCaptchaFields(self, response):
        fields = {
            'amzn': response.xpath("//form[@action='/errors/validateCaptcha']/input[@name='amzn']/@value").get(),
            'amzn-r': response.xpath("//form[@action='/errors/validateCaptcha']/input[@name='amzn-r']/@value").get(),
            'field-keywords': ''
        }
        return fields

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
        form_fields = self.findCaptchaFields(response)
        form_fields['field-keywords'] = captchaSolution
        formRequest = FormRequest.from_response(response, formnumber=0, formdata=form_fields)
        formRequest.meta[RETRY_KEY] = request.meta.get('captcha_retries', 0) + 1
        return formRequest
