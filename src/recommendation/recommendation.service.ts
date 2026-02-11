import { Injectable, InternalServerErrorException } from '@nestjs/common';

@Injectable()
export class RecommendationService {
  private readonly ragBaseUrl = process.env.RAG_SERVICE_URL;

  async ragAnswer(queryText: string, topK = 3) {
    if (!this.ragBaseUrl) {
      throw new InternalServerErrorException('RAG_SERVICE_URL is not configured');
    }

    const res = await fetch(`${this.ragBaseUrl}/rag/answer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ queryText, topK }),
    });

    if (!res.ok) {
      const err = await res.text();
      throw new InternalServerErrorException(`RAG service error: ${err}`);
    }

    return res.json(); // { answer, sources }
  }

    async embedOne(courseCode: string) {
    if (!this.ragBaseUrl) {
      throw new InternalServerErrorException('RAG_SERVICE_URL is not configured');
    }

    const res = await fetch(`${this.ragBaseUrl}/courses/embed-one`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ courseCode }),
    });

    if (!res.ok) {
      const err = await res.text();
      throw new InternalServerErrorException(`RAG service error: ${err}`);
    }

    return res.json(); // { ok, courseCode, dim }
  }

  async embedMissing(limit = 50) {
    if (!this.ragBaseUrl) {
      throw new InternalServerErrorException('RAG_SERVICE_URL is not configured');
    }

    const res = await fetch(`${this.ragBaseUrl}/courses/embed-missing`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ limit }),
    });

    if (!res.ok) {
      const err = await res.text();
      throw new InternalServerErrorException(`RAG service error: ${err}`);
    }

    return res.json(); // { ok, updated, failed }
  }

}
