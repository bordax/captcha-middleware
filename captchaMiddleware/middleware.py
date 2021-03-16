import logging
import locale
from scrapy.http import FormRequest
from scrapy.exceptions import IgnoreRequest
from captchaMiddleware.solver import solveCaptcha

logger = logging.getLogger(__name__)


class CaptchaMiddleware(object):
    """Checks a page for a CAPTCHA test and, if present, submits a solution for it"""

    def findCaptchaImageUrl(self, response):
        captcha_form = response.xpath("//form[@action='/errors/validateCaptcha']")
        if not captcha_form:
            return None
        image_url = captcha_form.xpath("//div[@class='a-row a-text-center']/img/@src").get()
        return image_url


    def find_captcha_fields(self, response):
        fields = {
            'amzn': response.xpath("//form[@action='/errors/validateCaptcha']/input[@name='amzn']/@value").get(),
            'amzn-r': response.xpath("//form[@action='/errors/validateCaptcha']/input[@name='amzn-r']/@value").get(),
            'field-keywords': ''
        }
        return fields


    def process_response(self, request, response, spider):
        captcha_url = self.findCaptchaImageUrl(response)
        if captcha_url is None:
            logger.debug(f'No captcha found on {response.url}')
            return response; # No CAPTCHA is present
        logger.info(f'Captcha found on {response.url}: {captcha_url}')

        captcha_solution = solveCaptcha(imgUrl=captcha_url, brazen=True)
        if captcha_solution is None:
            logger.error("CAPTCHA page detected, but no solution was proposed.")
            raise IgnoreRequest

        # Return a request to submit the captcha
        logger.info("Submitting solution %s for CAPTCHA at %s", captcha_solution, captcha_url)
        form_fields = self.find_captcha_fields(response)
        form_fields['field-keywords'] = captcha_solution
        form_request = FormRequest.from_response(response, formdata=form_fields)

        return form_request