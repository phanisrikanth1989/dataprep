"""
SendMail - Sends an email using SMTP.

Talend equivalent: tSendMail

This component sends emails via SMTP server with support for authentication,
SSL/TLS encryption, attachments, and multiple recipients (to, cc, bcc).
"""
import logging
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

from ...base_component import BaseComponent
from ...exceptions import ComponentExecutionError, ConfigurationError, FileOperationError

logger = logging.getLogger(__name__)


class SendMailComponent(BaseComponent):
    """
    Sends email messages via SMTP with support for authentication and attachments.

    Configuration:
        smtp_host (str): SMTP server hostname. Required.
        smtp_port (int): SMTP server port. Default: 25
        from_email (str): Sender email address. Required.
        to (list): List of recipient email addresses. Required.
        cc (list): List of CC email addresses. Default: []
        bcc (list): List of BCC email addresses. Default: []
        subject (str): Email subject line. Default: ""
        message (str): Email body text. Default: ""
        attachments (list): List of file paths to attach. Default: []
        auth_username (str): SMTP authentication username. Optional.
        auth_password (str): SMTP authentication password. Optional.
        ssl (bool): Use SSL connection. Default: False
        starttls (bool): Use STARTTLS encryption. Default: False
        text_subtype (str): MIME text subtype (plain/html). Default: "plain"
        encoding (str): Email encoding. Default: "utf-8"
        die_on_error (bool): Fail job on email error. Default: True

    Inputs:
        None: This component does not process input data

    Outputs:
        None: This component does not produce output data

    Statistics:
        NB_LINE: Always 0 (no data processing)
        NB_LINE_OK: Always 0 (no data processing)
        NB_LINE_REJECT: Always 0 (no data processing)

    Example configuration:
    {
        "smtp_host": "smtp.company.com",
        "smtp_port": 587,
        "from_email": "noreply@company.com",
        "to": ["admin@company.com"],
        "subject": "ETL Job Notification",
        "message": "Job completed successfully",
        "starttls": true,
        "auth_username": "smtp_user",
        "auth_password": "smtp_pass",
        "die_on_error": true
    }

    Notes:
        - Component will attempt to send email during job execution
        - Authentication is optional but recommended for production use
        - Supports both SSL and STARTTLS encryption methods
        - File attachments are read from local filesystem
    """

    # Class constants
    DEFAULT_SMTP_PORT = 25
    DEFAULT_TEXT_SUBTYPE = "plain"
    DEFAULT_ENCODING = "utf-8"

    def _validate_config(self) -> List[str]:
        """
        Validate component configuration.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Required fields
        required_fields = ['smtp_host', 'from_email', 'to']
        for field in required_fields:
            if not self.config.get(field):
                errors.append(f"Missing required config: {field}")

        # Validate email lists
        to_emails = self.config.get('to', [])
        if not isinstance(to_emails, list) or len(to_emails) == 0:
            errors.append("Config 'to' must be a non-empty list of email addresses")

        # Validate port if provided
        smtp_port = self.config.get('smtp_port')
        if smtp_port is not None:
            if not isinstance(smtp_port, int) or smtp_port < 1 or smtp_port > 65535:
                errors.append("Config 'smtp_port' must be an integer between 1 and 65535")

        # Validate optional lists
        for field in ['cc', 'bcc', 'attachments']:
            value = self.config.get(field)
            if value is not None and not isinstance(value, list):
                errors.append(f"Config '{field}' must be a list")

        return errors

    def _process(self, input_data: Optional[Any] = None) -> Dict[str, Any]:
        """
        Send email based on configuration.

        Args:
            input_data: Input data (not used in this component)

        Returns:
            Empty dictionary as this component does not produce output

        Raises:
            ConfigurationError: If required configuration is missing or invalid
            FileOperationError: If attachment files cannot be read
            ComponentExecutionError: If email sending fails
        """
        logger.info(f"[{self.id}] Sending email started")

        # Validate configuration
        config_errors = self._validate_config()
        if config_errors:
            error_msg = "; ".join(config_errors)
            logger.error(f"[{self.id}] Configuration validation failed: {error_msg}")
            raise ConfigurationError(f"Invalid configuration: {error_msg}")

        try:
            # Extract configuration with defaults
            smtp_host = self.config.get('smtp_host')
            smtp_port = self.config.get('smtp_port', self.DEFAULT_SMTP_PORT)
            from_email = self.config.get('from_email')
            to_emails = self.config.get('to', [])
            cc_emails = self.config.get('cc', [])
            bcc_emails = self.config.get('bcc', [])
            subject = self.config.get('subject', '')
            message = self.config.get('message', '')
            attachments = self.config.get('attachments', [])
            auth_username = self.config.get('auth_username')
            auth_password = self.config.get('auth_password')
            use_ssl = self.config.get('ssl', False)
            use_starttls = self.config.get('starttls', False)
            die_on_error = self.config.get('die_on_error', True)

            # Create the email message
            logger.debug(f"[{self.id}] Creating email message: to={len(to_emails)} recipients")
            msg = MIMEMultipart()
            msg['From'] = from_email
            msg['To'] = ", ".join(to_emails)
            msg['Cc'] = ", ".join(cc_emails)
            msg['Subject'] = subject

            # Add the email body
            body = MIMEText(
                message,
                self.config.get('text_subtype', self.DEFAULT_TEXT_SUBTYPE),
                self.config.get('encoding', self.DEFAULT_ENCODING)
            )
            msg.attach(body)

            # Add attachments
            for attachment in attachments:
                try:
                    logger.debug(f"[{self.id}] Adding attachment: {attachment}")
                    part = MIMEBase('application', 'octet-stream')
                    with open(attachment, 'rb') as file:
                        part.set_payload(file.read())
                    encoders.encode_base64(part)
                    part.add_header('Content-Disposition', f'attachment; filename={attachment}')
                    msg.attach(part)
                except FileNotFoundError as e:
                    error_msg = f"Attachment file not found: {attachment}"
                    logger.error(f"[{self.id}] {error_msg}")
                    if die_on_error:
                        raise FileOperationError(error_msg) from e
                    else:
                        logger.warning(f"[{self.id}] Skipping missing attachment: {attachment}")
                except Exception as e:
                    error_msg = f"Failed to read attachment: {attachment}: {str(e)}"
                    logger.error(f"[{self.id}] {error_msg}")
                    if die_on_error:
                        raise FileOperationError(error_msg) from e
                    else:
                        logger.warning(f"[{self.id}] Skipping unreadable attachment: {attachment}")

            # Send the email
            logger.debug(f"[{self.id}] Connecting to SMTP server: {smtp_host}:{smtp_port}")
            if use_ssl:
                server = smtplib.SMTP_SSL(smtp_host, smtp_port)
            else:
                server = smtplib.SMTP(smtp_host, smtp_port)

            if use_starttls:
                logger.debug(f"[{self.id}] Starting TLS encryption")
                server.starttls()

            if auth_username and auth_password:
                logger.debug(f"[{self.id}] Authenticating with username: {auth_username}")
                server.login(auth_username, auth_password)

            all_recipients = to_emails + cc_emails + bcc_emails
            logger.debug(f"[{self.id}] Sending email to {len(all_recipients)} total recipients")
            server.sendmail(from_email, all_recipients, msg.as_string())
            server.quit()

            logger.info(f"[{self.id}] Email sent successfully to {len(all_recipients)} recipients")

        except (smtplib.SMTPException, ConnectionError, OSError) as e:
            error_msg = f"Failed to send email: {str(e)}"
            logger.error(f"[{self.id}] {error_msg}")
            if die_on_error:
                raise ComponentExecutionError(self.id, error_msg, e) from e
            else:
                logger.warning(f"[{self.id}] Email sending failed but continuing due to die_on_error=False")

        except Exception as e:
            error_msg = f"Unexpected error sending email: {str(e)}"
            logger.error(f"[{self.id}] {error_msg}")
            if die_on_error:
                raise ComponentExecutionError(self.id, error_msg, e) from e

        # Update statistics (no data processing for this component)
        self._update_stats(0, 0, 0)
        logger.info(f"[{self.id}] Email sending complete")

        return {}

    def validate_config(self) -> bool:
        """
        Validates the component configuration.

        Returns:
            True if the configuration is valid, False otherwise.
        """
        required_fields = ['smtp_host', 'from_email', 'to']
        for field in required_fields:
            if not self.config.get(field):
                logger.error(f"[{self.id}] Missing required parameter '{field}'.")
                return False

        return True