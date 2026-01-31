import { Injectable, UnauthorizedException } from '@nestjs/common';
import { PassportStrategy } from '@nestjs/passport';
import { Strategy } from 'passport-google-oauth20';
import { AuthService } from './auth.service';

@Injectable()
export class GoogleStrategy extends PassportStrategy(Strategy, 'google') {
  constructor(private authService: AuthService) {
    super({
      clientID: process.env.GOOGLE_CLIENT_ID,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET,
      callbackURL: process.env.GOOGLE_CALLBACK_URL,
      scope: ['email', 'profile'],
    });
  }

  async validate(accessToken: string, refreshToken: string, profile: any) {
    const email = profile.emails?.[0]?.value;

    if (!email) {
      throw new UnauthorizedException('Email not found in Google profile');
    }

    // อนุญาตเฉพาะอีเมล KMITL
    // if (!email.endsWith('@kmitl.ac.th')) {
    //   throw new UnauthorizedException(
    //     'Allowed only for @kmitl.ac.th accounts.',
    //   );
    // }

    return {
      email,
      name: profile.displayName,
      picture: profile.photos?.[0]?.value,
      provider: profile.provider,
      providerId: profile.id,
    };
  }

  
}
