import nodemailer from 'nodemailer';
import { requestApproval } from '../approval/index.js';
import { loadConfig } from '../../config/index.js';

export async function sendEmail(to: string, subject: string, body: string) {
  const cfg = loadConfig();
  if (!cfg.smtp) throw new Error('SMTP not configured in ~/.walia/config.json');
  const approved = await requestApproval('email', JSON.stringify({ to, subject, body }, null, 2));
  if (!approved) throw new Error('Denied by user');
  const transporter = nodemailer.createTransport({
    host: cfg.smtp.host,
    port: cfg.smtp.port,
    auth: { user: cfg.smtp.user, pass: cfg.smtp.pass }
  });
  return transporter.sendMail({ from: cfg.smtp.from, to, subject, text: body });
}
