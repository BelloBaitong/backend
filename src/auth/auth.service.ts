import { Injectable, UnauthorizedException } from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';
import { UserService } from '../user/user.service';

@Injectable()
export class AuthService {
  constructor(
    private readonly userService: UserService,
    private readonly jwt: JwtService,
  ) {}

  async loginWithGoogle(googleUser: any) {
    if (!googleUser?.email) {
      throw new UnauthorizedException('Invalid Google user data');
    }

    const email: string = googleUser.email;

    // // ✅ จำกัดเฉพาะ @kmitl.ac.th
    // if (!email.endsWith('@kmitl.ac.th')) {
    //   throw new UnauthorizedException('อนุญาตเฉพาะอีเมล @kmitl.ac.th เท่านั้น');
    // }

    const user = await this.userService.findOrCreateGoogleUser({
      email,
      name: googleUser.name ?? email.split('@')[0],
      picture: googleUser.picture,
      provider: 'google',
      providerId: googleUser.providerId,
    });

    const token = await this.jwt.signAsync({
      sub: user.id,
      email: user.email,
    });

    return { token, user };
  }
}
