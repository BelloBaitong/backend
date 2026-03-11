import { Injectable } from '@nestjs/common';
import { HttpService } from '@nestjs/axios';
import { firstValueFrom } from 'rxjs';

@Injectable()
export class CourseAiService {
  constructor(private readonly http: HttpService) {}

  async getAiSummary(courseCode: string) {
    const baseUrl = process.env.RAG_SERVICE_URL;
    const url = `${baseUrl}/courses/summary`;

    const { data } = await firstValueFrom(
      this.http.post(url, { courseCode }),
    );

    return data; // { ok, status, summary, courseCode }
  }
}