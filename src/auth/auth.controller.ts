import { Controller, Get, Req, UseGuards, Res } from '@nestjs/common';
import { AuthGuard } from '@nestjs/passport';
import { AuthService } from './auth.service';
import type { Response } from 'express';
import { ConfigService } from '@nestjs/config';

@Controller('auth')
export class AuthController {
  constructor(
    private readonly authService: AuthService,
    private readonly config: ConfigService,
  ) {}

  @Get('google')
  @UseGuards(AuthGuard('google'))
  googleAuth() {
    return;
  }

  @Get('google/callback')
  @UseGuards(AuthGuard('google'))
  async googleAuthRedirect(@Req() req, @Res() res: Response) {
    const { token } = await this.authService.loginWithGoogle(req.user);

    const frontend = this.config.get<string>('FRONTEND_URL') ?? 'http://localhost:3000';

    // ส่ง token กลับไปหน้า frontend ที่คุณกำหนดเอง
    return res.redirect(`${frontend}/auth/callback?token=${encodeURIComponent(token)}`);
  }
}
